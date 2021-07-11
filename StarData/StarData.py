from typing import Callable, List, TypeVar, Dict, Optional
from .Error import *
import threading
import uuid
import json
from hashlib import md5
import time
import sys
from os.path import exists, isdir, join
from os import mkdir
import requests

M = TypeVar("M")


class Base:
    def __init__(self, api: str, private_key: str, salt: Callable[[], str], url: str, version: str):
        self.api = api
        self.private_key = private_key
        self.salt = salt
        self.url = url
        self.version = version
        self.local: Optional[str] = None
        self.wait = 0
        self.wait_lock = threading.Lock()

        try:
            response = requests.get(
                url=f"{self.url}/get_db_config",
                params={
                    "api": "ahdi1e3",
                    "version": "1.0.0",
                },
            )
            self.config = response.json()

            save_config_thread = threading.Thread(target=self.save_local_config)
            save_config_thread.start()
        except requests.exceptions.RequestException:
            self.config = self.get_config_from_local()

    def creat_local(self) -> bool:
        if self.local:
            if not exists(self.local):
                if isdir(self.local):
                    mkdir(self.local)
                    return True
                else:
                    return False
            else:
                return isdir(self.local)
        else:
            return False

    def save_local_config(self):
        self.wait_lock.acquire()
        self.wait += 1
        self.wait_lock.release()

        if self.creat_local():
            json_data = json.dumps(self.config)
            with open(join(self.local, 'config.json'), 'w') as f:
                f.write(json_data)

        self.wait_lock.acquire()
        self.wait += 1
        self.wait_lock.release()

    def get_config_from_local(self) -> dict:
        if self.creat_local():
            config = {}
            with open(join(self.local, 'config.json')) as f:
                read_str = f.read()

            if read_str and read_str != '':
                config = json.loads(read_str)

            return config

    def to_md5(self):
        md5_obj = md5()
        md5_obj.update(self.private_key.encode() + self.salt().encode())
        return md5_obj.hexdigest()

    def get_p_config(self, table_name: str, db_name: str) -> dict:
        for db in self.config['db']:
            if db['db_name'].lower() == db_name.lower():
                for table in db['db_table']:
                    if table['table_name'].lower() == table_name.lower():
                        return table['table_parameter']

    def is_private(self, db_name: str) -> bool:
        for db in self.config['db']:
            if db['db_name'].lower() == db_name.lower():
                return not db['public']

    def __del__(self):
        count = 0
        while self.wait != 0 and count <= 1000:
            time.sleep(0.1)
            count += 1


class Context:
    def __init__(self, base: Base, db_name: str, private: str = ''):
        self.base = base
        self.db_name = db_name
        self.private = private
        self.creat_on_remote = False
        self.get_value_mode = 0  # 0: Get back first, 1: Get first and then return, 2: Get once (Manual, loud)
        self.update_value_mode = 0  # 0: Automatic update (background) 1: Automatic update 2: Manual (save)
        self.creat_mode = 0.1  # 0: Automatic creat(.1 Background, .2: Front) 1: Manual (save .1 Background, .2: Front)
        self.max_destruct_time = sys.maxsize

        try:
            response = requests.get(
                url=f"{self.base.url}/easy_verification",
                params={
                    "api": base.api,
                    "private_key": base.private_key,
                    "salt": base.salt(),
                    "db_name": db_name + private,
                },
            )
            self.status_code = response.status_code
        except requests.exceptions.RequestException:
            self.status_code = -1
            raise VerificationError("There is an error in your API, key, salted string, and database name")

        if private != '':  # is a private context
            try:
                response = requests.get(
                    url=f"{self.base.url}/easy_is_creat",
                    params={
                        "api": self.base.api,
                        "db_name": self.db_name,
                        "context_id": private,
                    },
                )

                self.creat_on_remote = response.json()['value']
            except requests.exceptions.RequestException:
                pass

    def fetch(self, model: M) -> List[M]:
        res = []

        try:
            response = requests.get(
                url=f"{self.base.url}/easy_get_all",
                params={
                    "api": self.base.api,
                    "db_name": self.db_name + self.private,
                    "table_name": model.table_name,
                },
            )
            self.status_code = response.status_code
            json_data = response.json()
            if json_data['type'] == 'get':
                for table in json_data['value']:
                    m = model(self, False)
                    m.set_value_with_dict(table)
                    res.append(m)
            # TODO: Local
        except requests.exceptions.RequestException:
            raise FetchError(f"Unable to query data {model}")

        return res

    def creat(self) -> str:
        if self.base.is_private(self.db_name) and not self.creat_on_remote:
            try:
                response = requests.get(
                    url=f"{self.base.url}/creat_db",
                    params={
                        "api": "ahdi1e3",
                        "db_name": self.db_name,
                    },
                )

                self.private = response.json()['context_id']
                self.creat_on_remote = True
                return self.private
            except requests.exceptions.RequestException:
                # TODO: Save in the local
                return ""


class StarParameter:
    def __init__(self, value, primary: bool, not_null: bool, value_type: str):
        self.value = value
        self.primary = primary
        self.not_null = not_null
        self.value_type = value_type


class StarValue:
    def __init__(self, value_type: str, value, base: Base):
        self.value_type = value_type
        self.value = value
        self.base = base

    def return_helper(self, value_type: str, value):
        if self.value_type == value_type:
            return value
        else:
            raise StarTypeError(f"The type you should choose is {self.value_type}")

    def uuid(self) -> Optional[uuid.UUID]:
        if self.value is None:
            return None
        return self.return_helper('uuid', uuid.UUID("{" + str(self.value) + "}"))

    def str(self) -> Optional[str]:
        if self.value is None:
            return None
        return self.return_helper('string', str(self.value))


class StarEmpty:
    pass


def transfer_to_json_value(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    else:
        return value


def transfer_from_json_value(config: dict, name: str, value, base: Base):
    p_type = 'parameter_type'

    for p in config:
        if p["parameter_name"].upper() == name.upper():
            if p[p_type].lower() == 'uuid':
                return uuid.UUID("{" + str(value) + '}')
            elif p[p_type].lower() == 'string':
                return str(value)
            elif p[p_type].lower() == 'int':
                return int(value)
            elif p[p_type].lower() == 'double':
                return float(value)
            elif p[p_type].lower() == 'en_str':
                return str(value)
            elif p[p_type].lower() == 'context':
                context_data = str(value).split('-')
                if len(context_data) > 1:
                    return Context(base=base, db_name=context_data[0], private=context_data[1])
                else:
                    return Context(base=base, db_name=context_data[0])
            else:
                return value


class BaseModel:
    table_name: str
    primary_name: str

    def __init__(self, context: Context, creat: bool = True):
        self.context = context
        self.status_code = -1
        self.value: Dict[str, StarParameter] = {}
        self.update_lock = threading.Lock()
        self.creat_lock = threading.Lock()
        self.creating_lock = threading.Lock()
        self.wait_lock = threading.Lock()
        self.creat_on_remote = False
        self.creating = False
        self.wait = 0

        # Init Value dict
        for db in self.context.base.config['db']:
            if str(db['db_name']) == self.context.db_name:
                for table in db['db_table']:
                    if str(table['table_name']).lower() == self.table_name.lower():
                        for p in table['table_parameter']:
                            self.value[str(p['parameter_name']).upper()] = StarParameter(StarEmpty(), p['is_primary'],
                                                                                         p['not_null'],
                                                                                         p['parameter_type'])
                            if str(p['parameter_name']).upper() == self.primary_name.upper() \
                                    and p['parameter_type'] == 'uuid' and \
                                    p['not_null']:
                                # set default value
                                self.value[str(p['parameter_name']).upper()].value = uuid.uuid1()

        if creat:
            creat_thread = threading.Thread(target=self.try_creat)
            creat_thread.start()
        else:
            self.creat_on_remote = True

    def try_creat(self):
        self.add_wait()
        if self.creating or self.creat_on_remote:
            self.reduce_wait()
            return
        self.creating_lock.acquire()
        self.creating = True
        self.creating_lock.release()

        json_data = self.to_json()

        if json_data:
            try:
                response = requests.post(
                    url=f"{self.context.base.url}/insert",
                    params={
                        "api": self.context.base.api,
                    },
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                    },
                    data=json.dumps(json_data)
                )

                if response.json()['type'] == 'success':
                    self.creat_lock.acquire()
                    self.creat_on_remote = True
                    self.creat_lock.release()
            except requests.exceptions.RequestException:
                pass

        self.creating_lock.acquire()
        self.creating = False
        self.creating_lock.release()

        self.reduce_wait()

    def set_value_with_dict(self, data: dict):
        for p_name in self.value:
            self.update_lock.acquire()
            self.value[p_name.upper()].value = transfer_from_json_value(
                config=self.context.base.get_p_config(self.table_name, self.context.db_name),
                name=p_name,
                value=data[p_name.upper()],
                base=self.context.base
            )
            self.update_lock.release()

    def to_json(self) -> Optional[dict]:
        res = {
            "table_name": self.table_name,
            "db_name": self.context.db_name + self.context.private,
            "key": self.context.base.to_md5(),
            "insert_data": {}
        }

        insert_data = {}
        for p_name in self.value:
            # Is not null but value is none
            if self.value[p_name.upper()].not_null and \
                    (self.value[p_name.upper()].value is None or
                     isinstance(self.value[p_name.upper()].value, StarEmpty)):
                return None

            insert_data[p_name.upper()] = transfer_to_json_value(self.value[p_name.upper()].value)

        res['insert_data'] = insert_data

        return res

    def requests_value(self, name: str):
        try:
            response = requests.get(
                url=f"{self.context.base.url}/easy_get",
                params={
                    "api": self.context.base.api,
                    "db_name": self.context.db_name + self.context.private,
                    "table_name": self.table_name,
                    "name": name,
                    "value": self.value[self.primary_name.upper()].value,
                },
            )
            self.status_code = response.status_code
            json_data = response.json()
            if json_data['type'] == 'get':
                return json_data['value']
        except requests.exceptions.RequestException:
            return None

    def background_get_value(self, name):
        self.add_wait()
        res = self.requests_value(name)

        if res is None:
            if not self.value[name].not_null:
                self.update_lock.acquire()
                self.value[name.upper()].value = None
                self.update_lock.release()
        else:
            self.update_lock.acquire()
            self.value[name.upper()].value = res
            self.update_lock.release()

        self.reduce_wait()

    def get_value(self, name: str) -> StarValue:
        if isinstance(self.value[name.upper()].value, StarEmpty):
            # Get Value
            res = self.requests_value(name)

            if not res:
                self.update_lock.acquire()
                self.value[name.upper()].value = res
                self.update_lock.release()
                return res

            if self.value[name.upper()].not_null:
                raise StarGetValueError("We cannot communicate with StarData to obtain data, and your requested " +
                                        "value is not Null")
            else:
                self.update_lock.acquire()
                self.value[name.upper()].value = None
                self.update_lock.release()
                return StarValue(self.value[name.upper()].value_type, None, self.context.base)
        else:
            if self.creat_on_remote:
                requests_thread = threading.Thread(target=self.background_get_value, args=[name])
                requests_thread.start()
            return StarValue(self.value[name.upper()].value_type, self.value[name.upper()].value, self.context.base)

    def type_verification(self, name: str, value) -> bool:
        p_type = self.value[name.upper()].value_type.lower()
        if p_type == 'uuid':
            return isinstance(value, uuid.UUID)
        elif p_type == 'string':
            return isinstance(value, str)
        elif p_type == 'int':
            return isinstance(value, int)
        elif p_type == 'double':
            return isinstance(value, float)
        elif p_type == 'en_str':
            for c in str(value):
                if ord(c) > 126:
                    return False
            return isinstance(value, str)
        elif p_type == 'context':
            return isinstance(value, Context)
        else:
            return False

    def add_wait(self):
        self.wait_lock.acquire()
        self.wait += 1
        self.wait_lock.release()

    def reduce_wait(self):
        self.wait_lock.acquire()
        self.wait -= 1
        self.wait_lock.release()

    def update_value(self, name: str, value):
        self.add_wait()

        try:
            requests.post(
                url=f"{self.context.base.url}/east_set",
                params={
                    "api": self.context.base.api,
                },
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                },
                data=json.dumps({
                    "table_name": self.table_name,
                    "value": transfer_to_json_value(value),
                    "key": self.context.base.to_md5(),
                    "db_name": self.context.db_name + self.context.private,
                    "primary": transfer_to_json_value(self.value[self.primary_name.upper()].value),
                    "name": name.upper()
                })
            )
        except requests.exceptions.RequestException:
            print('HTTP Request failed')

        self.reduce_wait()

    def set_value(self, name: str, value):
        if not self.type_verification(name, value):
            return

        self.update_lock.acquire()
        self.value[name.upper()].value = value
        self.update_lock.release()

        if not self.creat_on_remote:
            creat_thread = threading.Thread(target=self.try_creat)
            creat_thread.start()
        else:
            update_thread = threading.Thread(target=self.update_value, kwargs={'name': name, 'value': value})
            update_thread.start()

    def __del__(self):
        wait_time = 0
        while self.wait != 0 and wait_time <= self.context.max_destruct_time:
            time.sleep(0.1)
            wait_time += 1

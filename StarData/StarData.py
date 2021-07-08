from typing import Callable, List, TypeVar, Dict, Optional
import requests
from .Error import *
import threading
import uuid
import json

M = TypeVar("M")


class Base:
    def __init__(self, api: str, private_key: str, salt: Callable[[], str], url: str, version: str):
        self.api = api
        self.private_key = private_key
        self.salt = salt
        self.url = url
        self.version = version

        try:
            response = requests.get(
                url=f"{self.url}/get_db_config",
                params={
                    "api": "ahdi1e3",
                    "version": "1.0.0",
                },
            )
            self.config = response.json()
        except requests.exceptions.RequestException:
            self.config = {}
            # TODO: Use local config file

    local: Optional[str] = None


class Context:
    def __init__(self, base: Base, db_name: str):
        self.base = base
        self.db_name = db_name
        self.get_value_mode = 0  # 0: Get back first, 1: Get first and then return, 2: Get once (Manual, loud)
        self.update_value_mode = 0  # 0: Automatic update (background) 1: Automatic update 2: Manual (save)
        self.creat_mode = 0.1  # 0: Automatic creat(.1 Background, .2: Front) 1: Manual (save .1 Background, .2: Front)

        try:
            response = requests.get(
                url=f"{self.base.url}/easy_verification",
                params={
                    "api": base.api,
                    "private_key": base.private_key,
                    "salt": base.salt(),
                    "db_name": db_name,
                },
            )
            self.status_code = response.status_code
        except requests.exceptions.RequestException:
            self.status_code = -1
            raise VerificationError("There is an error in your API, key, salted string, and database name")

    def fetch(self, model: M) -> List[M]:
        res = []

        try:
            response = requests.get(
                url=f"{self.base.url}/easy_get_all",
                params={
                    "api": self.base.api,
                    "db_name": self.db_name,
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
        return self.return_helper('str', str(self.value))


class StarEmpty:
    pass


class BaseModel:
    table_name: str
    primary_name: str
    value: Dict[str, StarParameter] = {}
    update_lock = threading.Lock()
    creat_lock = threading.Lock()
    creating_lock = threading.Lock()
    creat_on_remote = False
    creating = False

    def __init__(self, context: Context, creat: bool = True):
        self.context = context
        self.status_code = -1

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

    def try_creat(self):
        if self.creating or self.creat_on_remote:
            return
        self.creating_lock.acquire()
        self.creating = True
        self.creating_lock.release()

        # TODO: Creat on Remote

        self.creat_lock.acquire()
        self.creat_on_remote = True
        self.creat_lock.release()

        self.creating_lock.acquire()
        self.creating = False
        self.creating_lock.release()

    def set_value_with_dict(self, data: dict):
        for p_name in self.value:
            self.update_lock.acquire()
            self.value[p_name].value = data[p_name.upper()]
            self.update_lock.release()

    def requests_value(self, name: str):
        try:
            response = requests.get(
                url=f"{self.context.base.url}/easy_get",
                params={
                    "api": self.context.base.api,
                    "db_name": self.context.db_name,
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
        res = self.requests_value(name)

        if res is None:
            if not self.value[name].not_null:
                self.update_lock.acquire()
                self.value[name].value = None
                self.update_lock.release()
        else:
            self.update_lock.acquire()
            self.value[name].value = res
            self.update_lock.release()

    def get_value(self, name: str) -> StarValue:
        name = name.upper()
        if isinstance(self.value[name].value, StarEmpty):
            # Get Value
            res = self.requests_value(name)

            if not res:
                self.update_lock.acquire()
                self.value[name].value = res
                self.update_lock.release()
                return res

            if self.value[name].not_null:
                raise StarGetValueError("We cannot communicate with StarData to obtain data, and your requested " +
                                        "value is not Null")
            else:
                self.update_lock.acquire()
                self.value[name].value = None
                self.update_lock.release()
                return StarValue(self.value[name].value_type, None, self.context.base)
        else:
            if self.creat_on_remote:
                requests_thread = threading.Thread(target=self.background_get_value, args=[name])
                requests_thread.start()
            return StarValue(self.value[name].value_type, self.value[name].value, self.context.base)

    def set_value(self, name: str, value):
        if not self.creat_on_remote:
            creat_thread = threading.Thread(target=self.try_creat)
            creat_thread.start()
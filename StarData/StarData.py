from typing import Callable, List, TypeVar, Dict
import requests
from .StarValue import *
from .Error import *
import threading

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
        self.creat_mode = 0  # 0: Automatic creat 1: Manual (save)

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


class BaseModel:
    table_name: str
    primary_name: str
    value: Dict[str, StarParameter] = {}

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
            pass

    def set_value_with_dict(self, data: dict):
        for p_name in self.value:
            self.value[p_name].value = data[p_name.upper()]

    def requests_value(self, name: str) -> Optional[StarValue]:
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
                return StarValue(self.value[name].value_type, json_data['value'])
        except requests.exceptions.RequestException:
            return None

    def background_get_value(self, name: str):
        pass

    def get_value(self, name: str) -> StarValue:
        name = name.upper()
        if isinstance(self.value[name].value, StarEmpty):
            # Get Value
            res = self.requests_value(name)

            if not res:
                return res

            if self.value[name].not_null:
                raise StarGetValueError("We cannot communicate with StarData to obtain data, and your requested " +
                                        "value is not Null")
            else:
                return StarValue(self.value[name].value_type, None)
        else:
            requests_thread = threading.Thread(target=self.background_get_value, args=name)
            requests_thread.start()
            return StarValue(self.value[name].value_type, self.value[name].value)

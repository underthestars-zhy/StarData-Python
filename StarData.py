from hashlib import md5
import requests


class BaseData:
    api = ""
    key = ""
    salt = ""
    url = ""
    db_name = ""
    table_name = ""
    primary = None

    def get_md5(self) -> str:
        md5_obj = md5()
        md5_obj.update(self.key.encode() + self.salt.encode())
        return md5_obj.hexdigest()

    def get_value(self, name):
        try:
            response = requests.get(
                url=f"{self.url}/easy_get",
                params={
                    "api": self.api,
                    "db_name": self.db_name,
                    "table_name": self.table_name,
                    "name": name,
                    "value": self.primary,
                },
            )
            return dict(response.json())['value']
        except requests.exceptions.RequestException:
            return None


def get_all_items(model) -> list:
    res = []
    try:
        response = requests.get(
            url=f"{model.url}/easy_get_all",
            params={
                "api": model.api,
                "db_name": model.db_name,
                "table_name": model.table_name
            },
        )
        items = dict(response.json())['value']
    except requests.exceptions.RequestException:
        items = []

    for item in items:
        m = model()
        m.primary = item
        res.append(m)

    return res

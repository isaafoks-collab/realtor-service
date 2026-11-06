"""Проверка городов из regions.yaml. Запуск: python check_cities.py"""
import yaml
from httpclient import session

def main():
    with open("regions.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ok = True
    for city in cfg["cities"]:
        rid = city.get("cian_region_id")
        name = city["name"]
        status = "OK"
        if not rid:
            status = "НЕТ В CIANPARSER"; ok = False
        else:
            try:
                r = session().get("https://www.cian.ru/cat.php",
                                  params={"deal_type": "sale", "offer_type": "flat", "region": rid},
                                  timeout=15)
                if r.status_code != 200:
                    status = f"HTTP {r.status_code}"
            except Exception as e:
                status = f"ERR {e.__class__.__name__}"
        print(f"{name:20} region_id={rid}  {status}")
    print("ИТОГ:", "OK" if ok else "ЕСТЬ ПРОБЛЕМЫ")

if __name__ == "__main__":
    main()

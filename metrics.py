# -*- coding: utf-8 -*-
"""A4: метрики скорости уведомлений — среднее и p95 задержек.

Каналы задержек:
- публикование → обнаружение: published_at → detected_at;
- обнаружение → отправка: detected_at → sent_at.
Печать human-текстом: «в среднем 6.2 мин, p95 9.8 мин (n=141)».
"""
import math
import sqlite3
from datetime import datetime, timezone


def to_utc(value):
    """ISO-строка (учёт зон) или старый формат cian → aware-UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def delay_seconds(start, end):
    """Секунды между двумя ISO-строками; отрицательное/непонятное → None."""
    a, b = to_utc(start), to_utc(end)
    if a is None or b is None:
        return None
    diff = (b - a).total_seconds()
    return diff if diff >= 0 else None


def summarize(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return {"n": 0, "avg": None, "p95": None, "max": None}
    p95_idx = max(0, math.ceil(0.95 * len(vals)) - 1)
    return {
        "n": len(vals),
        "avg": sum(vals) / len(vals),
        "p95": vals[p95_idx],
        "max": vals[-1],
    }


def collect(conn):
    rows = conn.execute(
        "SELECT published_at, detected_at, sent_at FROM listings "
        "WHERE detected_at IS NOT NULL").fetchall()
    pub_to_det = []
    det_to_sent = []
    for published, detected, sent in rows:
        d = delay_seconds(published, detected)
        if d is not None:
            pub_to_det.append(d)
        if sent:
            d2 = delay_seconds(detected, sent)
            if d2 is not None:
                det_to_sent.append(d2)
    return pub_to_det, det_to_sent


def fmt_summary(label, summary):
    if summary["n"] == 0:
        return "%s: пока нет измерений" % label
    n = summary["n"]
    return ("%s: в среднем %.1f мин, p95 %.1f мин (наблюдений: %d, максимум %.1f мин)"
            % (label, summary["avg"] / 60, summary["p95"] / 60, n,
               summary["max"] / 60))


def report_text(conn):
    pub, sent = collect(conn)
    lines = [
        "Метрики скорости (A4):",
        " " + fmt_summary("[Публикация → обнаружение]", summarize(pub)),
        " " + fmt_summary("[Обнаружение → отправка]", summarize(sent)),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    con = sqlite3.connect("listings.db")
    print(report_text(con))
    con.close()

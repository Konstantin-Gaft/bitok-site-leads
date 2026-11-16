#!/usr/bin/env python3
"""Новая заявка в Monday «Входящие с сайта» → Telegram. Запускается GitHub Actions по крону,
работает при выключенном маке. Секреты: MONDAY_API_TOKEN, BOT_TOKEN, TG_CHAT_ID. Состояние — seen.json."""
import json, os, re, urllib.request
import enrich

BOARD, GROUP = 9027825117, "group_mm34z8fw"
SKIP_COLS = {"Next Touch", "Priority", "Stage"}
SEEN = "seen.json"


def post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def items():
    q = ('query{boards(ids:[%d]){groups(ids:["%s"]){items_page(limit:25,query_params:{order_by:'
         '[{column_id:"__creation_log__",direction:desc}]}){items{id name created_at '
         'updates(limit:3){text_body} column_values{id text column{title}}}}}}}' % (BOARD, GROUP))
    r = post("https://api.monday.com/v2", {"query": q},
             {"Authorization": os.environ["MONDAY_API_TOKEN"], "API-Version": "2024-10"})
    return r["data"]["boards"][0]["groups"][0]["items_page"]["items"]


def esc(s):
    return re.sub(r"([_*`\[])", r"\\\1", s or "")


def render(it, note=""):
    lines = ["🆕 *Заявка с сайта*"]
    for c in it["column_values"]:
        k, v = c["column"]["title"], (c["text"] or "").strip()
        if not v or k in SKIP_COLS: continue
        if k == "TG" and not v.startswith("@"): v = "@" + v
        lines.append(f"*{esc(k)}:* {esc(v)}")
    for u in it.get("updates") or []:
        t = (u.get("text_body") or "").strip()
        if t: lines.append("\n" + esc(t[:1500]))
    if note: lines.append("\n" + esc(note))
    lines.append(f"\n[Карточка в Monday](https://bitok-aml.monday.com/boards/{BOARD}/pulses/{it['id']})")
    return "\n".join(lines)[:4000]


COLS = {"tg": "text_mm45yrdd", "name": "text_mkqfaqq5", "company": "text_mkqf2rss", "email": "email_mm35py0p",
        "text": "text_mm35dcyr", "utm": "text_mm7az72"}


def enriched(it):
    """Подпись «нашёл ТГ / спам». Найденный ник пишем в карточку, вердикт — в Notes. Сбой не мешает уведомлению."""
    try:
        by = {c["id"]: (c["text"] or "") for c in it["column_values"]}
        note, handle = enrich.verdict({k: by.get(v, "") for k, v in COLS.items()})
        vals = {"text_mkqfhsx0": note.replace("\n", ". ")} if not by.get("text_mkqfhsx0") else {}
        if handle and by.get(COLS["tg"], "").lstrip("@").lower() != handle.lower():
            vals[COLS["tg"]] = "@" + handle
        if vals:
            m = ("mutation($b:ID!,$i:ID!,$v:JSON!){change_multiple_column_values(board_id:$b,item_id:$i,"
                 "column_values:$v){id}}")
            post("https://api.monday.com/v2", {"query": m, "variables": {"b": str(BOARD), "i": it["id"], "v": json.dumps(vals)}},
                 {"Authorization": os.environ["MONDAY_API_TOKEN"], "API-Version": "2024-10"})
        return note
    except Exception as e:
        print("enrich error", str(e)[:120]); return ""


def tg(text, md=True):
    body = {"chat_id": os.environ["TG_CHAT_ID"], "text": text, "disable_web_page_preview": True}
    if md: body["parse_mode"] = "Markdown"
    try:
        return post(f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}/sendMessage", body, {}).get("ok")
    except Exception as e:
        print("tg error", str(e)[:120]); return False


def main():
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else []
    its = items()
    if not seen:
        json.dump([i["id"] for i in its], open(SEEN, "w")); print("init", len(its)); return
    new = [i for i in reversed(its) if i["id"] not in seen]
    for it in new:
        txt = render(it, enriched(it))
        if tg(txt) or tg(re.sub(r"[*\\]", "", txt), md=False):
            seen.append(it["id"]); print("sent", it["id"])
    json.dump(seen[-500:], open(SEEN, "w"))


if __name__ == "__main__":
    main()

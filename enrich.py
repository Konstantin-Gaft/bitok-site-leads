#!/usr/bin/env python3
"""Подпись к заявке: «нашёл ТГ» или «спам, рекомендую к удалению». Без сессий: только публичная страница t.me.

Кандидаты в ники: поле TG (ник, ссылка t.me, вариант с точкой → подчёркивание/слитно), имя ящика почты.
Ник засчитан, когда страница t.me существует и это человек, а не канал; ник не из поля TG — только если
имя в профиле совпадает с именем из заявки. Телефон без сессии не пробить: об этом пишем в подписи.
"""
import re, urllib.request

FREE = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "mail.ru", "yandex.ru", "icloud.com", "proton.me",
        "protonmail.com", "bk.ru", "list.ru", "inbox.ru", "ya.ru", "live.com", "aol.com", "gmx.com", "rambler.ru"}
NOT_TG = re.compile(r"^(whats?app|вацап|ватсап|вотсап|viber|telegram|телеграм|tg|тг|нет|no|none|-+)$", re.I)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def page(handle):
    """→ {'title','bio','kind'} или None, если такого ника нет."""
    try:
        html = urllib.request.urlopen(urllib.request.Request(f"https://t.me/{handle}", headers=UA), timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'og:title" content="([^"]*)"', html)
    title = (m.group(1) if m else "").strip()
    if not title or title.startswith("Telegram: Contact"):
        return None
    d = re.search(r'og:description" content="([^"]*)"', html)
    extra = re.search(r'tgme_page_extra">([^<]*)', html)
    extra = (extra.group(1) if extra else "").lower()
    kind = "канал/группа" if re.search(r"subscriber|member", extra) else ("бот" if handle.lower().endswith("bot") else "человек")
    bio = (d.group(1) if d else "").strip()
    return {"title": title, "bio": "" if bio.startswith("You can contact") else bio, "kind": kind}


def handles(tg_field, email):
    """[(ник, откуда)] — сначала то, что человек указал сам."""
    out, raw = [], (tg_field or "").strip()
    for tok in re.findall(r"(?:t\.me/|@)?([A-Za-z][A-Za-z0-9_.]{3,31})", raw):
        if NOT_TG.match(tok) or tok.lower() in ("https", "http", "t.me"):
            continue
        for v in dict.fromkeys([tok, tok.replace(".", "_"), tok.replace(".", ""), tok.split(".")[0]]):
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", v):
                out.append((v, "поле TG" if v == tok else "поле TG, вариант"))
    local = (email or "").split("@")[0]
    for v in dict.fromkeys([local.replace(".", "_"), local.replace(".", "")]):
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", v) and v.lower() not in {h.lower() for h, _ in out}:
            out.append((v, "по почте"))
    return out[:6]


def same_person(title, name):
    a = {w for w in re.findall(r"[^\W\d_]{3,}", (title or "").lower())}
    b = {w for w in re.findall(r"[^\W\d_]{3,}", (name or "").lower())}
    return bool(a & b)


def phone(tg_field):
    d = re.sub(r"[^\d+]", "", tg_field or "")
    return d if re.fullmatch(r"\+\d{10,15}", d) and not re.search(r"[A-Za-z@]", tg_field or "") else ""   # без кода страны не пробить


def verdict(f):
    """f: name, tg, company, email, text, utm → (подпись, найденный ник или '')."""
    found, brand = None, None
    for h, src in handles(f.get("tg"), f.get("email")):
        p = page(h)
        if not p:
            continue
        if p["kind"] != "человек":
            if src == "поле TG":
                brand = brand or (h, p)          # бот или канал компании: не личный контакт, но заявка не пустая
            continue
        if src == "поле TG" or same_person(p["title"], f.get("name")):
            found = (h, src, p); break
    dom = (f.get("email") or "").lower().split("@")[-1]
    corp = bool(dom) and dom not in FREE
    company = (f.get("company") or "").strip()
    real_company = len(company) >= 4 and company.lower() not in (f.get("name") or "").lower() and "@" not in company \
        and bool(re.search(r"[A-Za-zА-Яа-я]{4,}", company))
    text = (f.get("text") or "").strip()
    cpc = "cpc" in (f.get("utm") or "")
    site = bool(re.search(r"[a-z0-9-]{3,}\.[a-z]{2,}", company.lower())) and "@" not in company   # в компании указан сайт
    score = 2 * corp + (len(text) >= 40) * 2 + bool(found) + real_company * (not cpc) + 2 * site + bool(brand)
    why = []
    if not corp: why.append(f"почта {dom or 'не указана'}")
    if not real_company: why.append("компании нет")
    if len(text) < 40: why.append("текста нет" if not text else "текст из пары слов")
    if cpc: why.append("пришёл с рекламы")
    lines = []
    if found:
        h, src, p = found
        lines.append(f"Нашёл ТГ: @{h} ({p['title']}" + (f", {p['bio'][:80]}" if p["bio"] else "") + f"; {src})")
    elif brand:
        lines.append(f"Личный ТГ не найден, в заявке {brand[1]['kind']} @{brand[0]} ({brand[1]['title']})")
    elif phone(f.get("tg")):
        lines.append(f"ТГ по нику не найден, есть номер {phone(f.get('tg'))}: пробью по номеру, когда мак в сети")
    else:
        lines.append("ТГ не найден")
    if score <= 1:
        lines.append("СПАМ, рекомендую к удалению: " + ", ".join(why))
    elif score == 2 and not corp:
        lines.append("Под вопросом: " + ", ".join(why))
    return "\n".join(lines), (found[0] if found else "")


if __name__ == "__main__":
    tests = [dict(name="Yosita Khumuang", tg="lallalin.n28", company="xdxchenge", email="noeyy.yosita.khumuang@gmail.com", text="", utm="utm_medium: cpc"),
             dict(name="Malzz", tg="", company="", email="malzzkece207@gmail.com", text="T", utm="utm_medium: cpc"),
             dict(name="Дмитрий", tg="@mtizima", company="Vondriba", email="mtizima@gmail.com", text="", utm=""),
             dict(name="Terence Cheong", tg="", company="BitKan", email="trade@bitkan.com", text="We're keen to explore the KYT/AML solutions for transaction monitoring", utm=""),
             dict(name="Irmintasun", tg="07515 677822", company="London", email="buscar42@yahoo.com", text="Investment", utm="cpc"),
             dict(name="Roy", tg="+971585295960 @EASTWESTLTD", company="", email="x@yahoo.com", text="Need 100 crypto checks per month - is there any plan for that?", utm=""),
             dict(name="Яна", tg="@finsmartex_bot", company="finsmartex.ru", email="finsmartbroker@mail.ru", text="", utm="")]
    for t in tests:
        print(t["name"], "→", verdict(t), "\n")

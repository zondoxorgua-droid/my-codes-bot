# my-codes-bot

Telegram-бот для управления кодами подарочных карт (Roblox, Apple, Overwatch и т.д.).

## Возможности

- **Группы и категории**: иерархия `Roblox → 200 Robux / 300 Robux / ...`. Можно создавать новые через бота.
- **Загрузка кодов**: админ присылает `.txt` файл или просто список сообщением — коды парсятся построчно, дубликаты игнорируются.
- **Выдача кодов**: пользователь выбирает группу → номинал → количество → формат (текстом или `.txt` файлом). Выданные коды помечаются использованными.
- **Остатки**: команда `/stock` показывает сколько кодов доступно по каждой категории.
- **История**: команда `/history` — что ты брал и когда.
- **Роли**: главный админ (`ROOT_ADMIN_ID`) выдаёт доступ другим пользователям через админ-панель.

## Запуск локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактировать .env: BOT_TOKEN и ROOT_ADMIN_ID
python -m app.bot
```

## Деплой на Ubuntu (systemd)

```bash
# на сервере
cd /root
git clone https://github.com/<user>/my-codes-bot.git
cd my-codes-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env  # вписать BOT_TOKEN и ROOT_ADMIN_ID

# установить unit
cp my-codes-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now my-codes-bot
journalctl -u my-codes-bot -n 50 --no-pager
```

## Обновление

```bash
cd /root/my-codes-bot
git pull origin main
systemctl restart my-codes-bot
journalctl -u my-codes-bot -n 50 --no-pager
```

## Получение `user_id`

Напиши в [@userinfobot](https://t.me/userinfobot) — он пришлёт твой Telegram ID.

# Production Deployment Guide

## Требования
- Linux server (Ubuntu 20.04+ / Debian 11+ / CentOS 8+)
- Docker 20.10+
- Docker Compose v2+
- Минимум 2GB RAM
- Минимум 10GB свободного места на диске

## Быстрый старт на сервере

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/Baurzhanovvv/document-bot-03.git
cd document-bot-03
```

### 2. Настройте .env файл
```bash
cp .env.production .env
nano .env  # или vim .env
```

Заполните обязательные параметры:
- `BOT_TOKEN` - токен Telegram бота от @BotFather
- `ADMIN_IDS` - ваш Telegram ID (получите от @userinfobot)
- `POSTGRES_PASSWORD` - надежный пароль для БД
- `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` - данные от ЮKassa

### 3. Запустите проект
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Проверьте статус
```bash
docker compose ps
docker compose logs -f app
```

## Управление

### Просмотр логов
```bash
# Все сервисы
docker compose logs -f

# Только бот
docker compose logs -f app

# Только база данных
docker compose logs -f db

# Последние 100 строк
docker compose logs --tail=100 app
```

### Перезапуск
```bash
docker compose restart app
```

### Остановка
```bash
docker compose down
```

### Полная остановка с удалением данных
```bash
docker compose down -v  # ВНИМАНИЕ: удалит все данные!
```

### Обновление проекта
```bash
git pull origin main
./deploy.sh
```

## Настройка Webhook для ЮKassa

1. Откройте личный кабинет ЮKassa
2. Перейдите в раздел "Настройки" → "Уведомления"
3. Добавьте webhook URL: `https://ваш-домен.com/webhook/yookassa`
4. Выберите метод: POST
5. Включите уведомления о платежах

## Настройка Nginx (опционально)

Если хотите использовать домен и SSL:

```nginx
server {
    listen 80;
    server_name ваш-домен.com;
    client_max_body_size 1300m;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

Установите SSL сертификат:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ваш-домен.com
```

## Мониторинг

### Проверка здоровья сервисов
```bash
# OpenSearch
curl http://localhost:9200/_cluster/health

# Tika
curl http://localhost:9998/tika

# PostgreSQL
docker compose exec db pg_isready -U postgres
```

### Использование ресурсов
```bash
docker stats
```

## Бэкап

### База данных
```bash
# Создать бэкап
docker compose exec db pg_dump -U postgres bot_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить бэкап
docker compose exec -T db psql -U postgres bot_db < backup_20241220_120000.sql
```

### Файлы пользователей
```bash
# Бэкап uploads
docker run --rm -v document_bot_3_uploads_data:/data -v $(pwd):/backup alpine tar czf /backup/uploads_backup_$(date +%Y%m%d).tar.gz -C /data .

# Восстановление
docker run --rm -v document_bot_3_uploads_data:/data -v $(pwd):/backup alpine tar xzf /backup/uploads_backup_20241220.tar.gz -C /data
```

## Troubleshooting

### Контейнер не запускается
```bash
docker compose logs app
```

### База данных не подключается
```bash
docker compose exec app ping db
docker compose exec db pg_isready -U postgres
```

### OpenSearch не работает
```bash
docker compose logs opensearch
# Проверьте, что хватает памяти (минимум 512MB для OpenSearch)
```

### Бот не отвечает
1. Проверьте логи: `docker compose logs -f app`
2. Проверьте токен бота в `.env`
3. Проверьте, что бот запущен: `docker compose ps`

## Безопасность

1. **Измените пароли** в `.env` на надежные
2. **Не публикуйте** файл `.env` в Git
3. **Настройте firewall**:
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```
4. **Регулярно обновляйте** Docker образы:
   ```bash
   docker compose pull
   ./deploy.sh
   ```

## Контакты поддержки

При возникновении проблем:
1. Проверьте логи: `docker compose logs -f`
2. Проверьте документацию: `QUICKSTART.md`, `PAYMENT_INTEGRATION.md`
3. Создайте issue в GitHub репозитории

#!/bin/bash

# Скрипт для развертывания проекта на production сервере

set -e

echo "🚀 Начинаем развертывание..."

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден! Создайте его перед запуском."
    exit 1
fi

# Остановка старых контейнеров
echo "⏹️  Останавливаем старые контейнеры..."
docker compose down || true

# Удаление старых образов (опционально)
echo "🗑️  Удаляем старые образы..."
docker compose down --rmi local || true

# Сборка образов
echo "🔨 Собираем образы..."
docker compose build --no-cache

# Запуск контейнеров
echo "▶️  Запускаем контейнеры..."
docker compose up -d

# Ожидание запуска всех сервисов
echo "⏳ Ждем запуска сервисов (30 сек)..."
sleep 30

# Проверка статуса
echo "✅ Проверяем статус контейнеров:"
docker compose ps

echo ""
echo "🎉 Развертывание завершено!"
echo ""
echo "📊 Проверьте логи командой: docker compose logs -f"
echo "🌐 Web UI доступен на: http://localhost:8000"
echo "🔍 OpenSearch доступен на: http://localhost:9200"
echo "📝 PostgreSQL доступен на: localhost:5433"

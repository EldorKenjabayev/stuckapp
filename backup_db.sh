#!/bin/bash

# Путь к оригинальному файлу базы данных
DB_PATH="/home/www/db.sqlite3"

# Путь к каталогу для резервного копирования
BACKUP_PATH="/home/www/backup"

# Имя файла резервной копии с датой и временем
BACKUP_FILENAME="db_backup_$(date +'%Y-%m-%d_%H-%M-%S').sqlite3"

# Создать каталог для резервных копий, если он не существует
mkdir -p $BACKUP_PATH

# Копирование файла базы данных в каталог для резервного копирования
cp $DB_PATH "$BACKUP_PATH/$BACKUP_FILENAME"

echo "Backup of database saved as $BACKUP_PATH/$BACKUP_FILENAME"

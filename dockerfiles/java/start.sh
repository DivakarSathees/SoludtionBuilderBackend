#!/bin/bash

echo "=== Fixing MariaDB directories ==="
mkdir -p /run/mysqld
chown -R mysql:mysql /run/mysqld

echo "=== Starting MariaDB ==="
mysqld --user=mysql --skip-log-error &
sleep 5

# Wait until MariaDB is ready
echo "=== Waiting for MariaDB socket ==="
for i in {1..20}; do
    if mysqladmin ping -u root -pexamly --silent; then
        echo "MariaDB is ready!"
        break
    fi
    echo "Waiting..."
    sleep 2
done

echo "=== Starting Spring Boot ==="
exec mvn spring-boot:run

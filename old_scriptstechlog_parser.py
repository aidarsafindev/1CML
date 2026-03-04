#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Парсер технологического журнала 1С в ClickHouse
Поддерживает форматы: log, log.gz
Версия: 1.0
"""

import os
import re
import gzip
import glob
from datetime import datetime
import logging
from pathlib import Path
import pandas as pd
from clickhouse_driver import Client
from clickhouse_driver.errors import Error as ClickHouseError
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('techlog_parser')

class TechLogParser:
    """Парсер технологического журнала 1С"""
    
    # Регулярные выражения для парсинга строк техжурнала
    PATTERNS = {
        'datetime': re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
        'duration': re.compile(r'duration=(\d+)'),
        'wait_time': re.compile(r'waitTime=(\d+)'),
        'lock_time': re.compile(r'lockTime=(\d+)'),
        'transaction': re.compile(r'transaction=(\d+)'),
        'connection': re.compile(r'connection=(\d+)'),
        'session': re.compile(r'session=(\d+)'),
        'user': re.compile(r'user="([^"]*)"'),
        'computer': re.compile(r'computer="([^"]*)"'),
        'app_id': re.compile(r'app-id="([^"]*)"'),
        'data': re.compile(r'data="([^"]*)"'),
        'context': re.compile(r'context="([^"]*)"'),
        'dbms': re.compile(r'dbms="([^"]*)"'),
        'dbpid': re.compile(r'dbpid=(\d+)'),
        'block': re.compile(r'block="([^"]*)"'),
        'func': re.compile(r'func="([^"]*)"'),
    }
    
    def __init__(self, clickhouse_host='localhost', clickhouse_port=9000,
                 database='techlog', table='techlog'):
        """
        Инициализация парсера
        
        Args:
            clickhouse_host: хост ClickHouse
            clickhouse_port: порт ClickHouse
            database: имя базы данных
            table: имя таблицы
        """
        self.client = Client(
            host=clickhouse_host,
            port=clickhouse_port,
            database=database,
            settings={'insert_quorum': 1}
        )
        self.database = database
        self.table = table
        
    def parse_log_line(self, line, file_date=None):
        """
        Парсинг одной строки техжурнала
        
        Args:
            line: строка лога
            file_date: дата из имени файла (если нет в строке)
        
        Returns:
            dict: распарсенные поля или None
        """
        try:
            parts = line.strip().split(',')
            if len(parts) < 5:
                return None
            
            # Базовая информация
            result = {
                'raw_line': line.strip()
            }
            
            # Время события
            time_part = parts[0].split(':')
            if len(time_part) >= 3:
                hour, minute, sec_ms = time_part[0], time_part[1], time_part[2]
                sec, ms = sec_ms.split('.')
                result['hour'] = int(hour)
                result['minute'] = int(minute)
                result['second'] = int(sec)
                result['millisecond'] = int(ms)
            
            # Остальные поля
            for part in parts[1:]:
                for key, pattern in self.PATTERNS.items():
                    if key in ('datetime',):
                        continue
                    match = pattern.search(part)
                    if match:
                        value = match.group(1)
                        # Преобразование типов
                        if key in ('duration', 'wait_time', 'lock_time', 'transaction',
                                  'connection', 'session', 'dbpid'):
                            result[key] = int(value)
                        else:
                            result[key] = value
                        break
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга строки: {line[:100]}... - {e}")
            return None
    
    def parse_file(self, file_path, batch_size=10000):
        """
        Парсинг файла техжурнала
        
        Args:
            file_path: путь к файлу
            batch_size: размер батча для вставки
        
        Returns:
            int: количество вставленных записей
        """
        logger.info(f"Парсинг файла: {file_path}")
        
        # Определяем дату из имени файла
        file_name = os.path.basename(file_path)
        file_date = None
        date_match = re.search(r'(\d{8})', file_name)
        if date_match:
            file_date = datetime.strptime(date_match.group(1), '%Y%m%d')
        
        open_func = gzip.open if file_path.endswith('.gz') else open
        mode = 'rt' if file_path.endswith('.gz') else 'r'
        
        batch = []
        total_inserted = 0
        
        try:
            with open_func(file_path, mode, encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self.parse_log_line(line, file_date)
                    if parsed:
                        # Добавляем дату из файла, если нет в строке
                        if file_date and 'date' not in parsed:
                            parsed['event_date'] = file_date.date()
                        
                        batch.append(parsed)
                        
                        if len(batch) >= batch_size:
                            self.insert_batch(batch)
                            total_inserted += len(batch)
                            batch = []
                            logger.info(f"Вставлено {total_inserted} записей")
                
                # Вставка остатка
                if batch:
                    self.insert_batch(batch)
                    total_inserted += len(batch)
            
            logger.info(f"Файл {file_path} обработан: {total_inserted} записей")
            return total_inserted
            
        except Exception as e:
            logger.error(f"Ошибка обработки файла {file_path}: {e}")
            return total_inserted
    
    def insert_batch(self, batch):
        """
        Вставка батча в ClickHouse
        
        Args:
            batch: список словарей с данными
        """
        if not batch:
            return
        
        try:
            # Подготовка данных для вставки
            columns = ['event_date', 'hour', 'minute', 'second', 'millisecond',
                      'duration', 'wait_time', 'lock_time', 'transaction',
                      'connection', 'session', 'user', 'computer', 'app_id',
                      'context', 'dbms', 'dbpid', 'func', 'raw_line']
            
            data = []
            for record in batch:
                row = [record.get(col) for col in columns]
                data.append(row)
            
            self.client.execute(
                f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES",
                data
            )
            
        except ClickHouseError as e:
            logger.error(f"Ошибка вставки в ClickHouse: {e}")
            raise
    
    def process_directory(self, directory, pattern='*.log', recursive=True,
                         max_workers=4):
        """
        Обработка директории с файлами техжурнала
        
        Args:
            directory: путь к директории
            pattern: паттерн файлов
            recursive: рекурсивный обход
            max_workers: количество потоков
        """
        path = Path(directory)
        if recursive:
            files = glob.glob(str(path / '**' / pattern), recursive=True)
        else:
            files = glob.glob(str(path / pattern))
        
        files.extend(glob.glob(str(path / '**' / (pattern + '.gz')), recursive=True))
        
        logger.info(f"Найдено {len(files)} файлов для обработки")
        
        total_records = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.parse_file, f): f for f in files}
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    records = future.result()
                    total_records += records
                    logger.info(f"Прогресс: {total_records} записей")
                except Exception as e:
                    logger.error(f"Ошибка в {file_path}: {e}")
        
        logger.info(f"Всего обработано: {total_records} записей")
        return total_records

def main():
    parser = argparse.ArgumentParser(description='Парсер техжурнала 1С в ClickHouse')
    parser.add_argument('--dir', required=True, help='Директория с техжурналом')
    parser.add_argument('--pattern', default='*.log', help='Паттерн файлов')
    parser.add_argument('--workers', type=int, default=4, help='Количество потоков')
    parser.add_argument('--host', default='localhost', help='Хост ClickHouse')
    parser.add_argument('--port', type=int, default=9000, help='Порт ClickHouse')
    parser.add_argument('--database', default='techlog', help='База данных')
    parser.add_argument('--table', default='techlog', help='Таблица')
    
    args = parser.parse_args()
    
    # Создание базы данных и таблицы, если не существуют
    client = Client(host=args.host, port=args.port)
    
    # Чтение схемы
    schema_path = Path(__file__).parent.parent / 'clickhouse' / 'schema.sql'
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    # Выполнение скрипта создания таблиц
    for statement in schema.split(';'):
        if statement.strip():
            try:
                client.execute(statement)
            except Exception as e:
                logger.warning(f"Ошибка при создании таблицы: {e}")
    
    # Запуск парсера
    parser = TechLogParser(
        clickhouse_host=args.host,
        clickhouse_port=args.port,
        database=args.database,
        table=args.table
    )
    
    parser.process_directory(args.dir, args.pattern, max_workers=args.workers)

if __name__ == "__main__":
    main()

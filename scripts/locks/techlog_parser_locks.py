#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Парсер техжурнала 1С с фокусом на блокировки и дедлоки
"""

import re
import gzip
from datetime import datetime
import logging
from typing import Optional, Dict, List
from clickhouse_driver import Client

logger = logging.getLogger('techlog_parser_locks')

class LockEventParser:
    """Парсер событий блокировок из техжурнала"""
    
    # Регулярные выражения для полей блокировок
    PATTERNS = {
        'datetime': re.compile(r'^(\d{4})(\d{2})(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
        'event_type': re.compile(r',([A-Z_]+),'),
        
        # Данные сессии
        'session': re.compile(r'session=(\d+)'),
        'transaction': re.compile(r'transaction=(\d+)'),
        'user': re.compile(r'userName="([^"]*)"'),
        'process': re.compile(r'processName=([^,]+)'),
        
        # Данные блокировки
        'table_name': re.compile(r'tableName="?([^",]+)"?'),
        'lock_type': re.compile(r'lockType="?([^",]+)"?'),
        'lock_mode': re.compile(r'lockMode="?([^",]+)"?'),
        'lock_name': re.compile(r'lockName="?([^",]+)"?'),
        
        # Метрики
        'lock_wait_time': re.compile(r'lockWaitTime=(\d+)'),
        'lock_time': re.compile(r'lockTime=(\d+)'),
        'dbpid': re.compile(r'dbpid=(\d+)'),
    }
    
    def __init__(self, client: Client):
        self.client = client
        self.batch = []
        self.batch_size = 5000
        
    def parse_line(self, line: str) -> Optional[Dict]:
        """Парсинг одной строки лога"""
        try:
            line = line.strip()
            if not line:
                return None
            
            # Парсим дату и время
            dt_match = self.PATTERNS['datetime'].search(line)
            if not dt_match:
                return None
            
            year, month, day, hour, minute, second, ms = map(int, dt_match.groups())
            event_datetime = datetime(year, month, day, hour, minute, second, ms * 1000)
            
            # Тип события
            type_match = self.PATTERNS['event_type'].search(line)
            event_type = type_match.group(1) if type_match else 'UNKNOWN'
            
            # Если это не событие блокировки - пропускаем для экономии
            if event_type not in ['LOCK', 'DEADLOCK', 'TTIMEOUT', 'SDBL']:
                return None
            
            # Извлекаем все поля
            result = {
                'event_date': event_datetime.date(),
                'event_hour': hour,
                'event_minute': minute,
                'event_datetime': event_datetime,
                'event_type': event_type,
            }
            
            # Извлекаем данные
            for key, pattern in self.PATTERNS.items():
                if key in ['datetime', 'event_type']:
                    continue
                
                match = pattern.search(line)
                if match:
                    value = match.group(1)
                    
                    # Преобразование типов
                    if key in ['session', 'transaction', 'lock_wait_time', 'lock_time', 'dbpid']:
                        try:
                            value = int(value)
                        except ValueError:
                            continue
                    
                    result[key] = value
            
            # Устанавливаем значения по умолчанию
            defaults = {
                'session': 0,
                'transaction': 0,
                'user': '',
                'process': '',
                'table_name': '',
                'lock_type': '',
                'lock_mode': '',
                'lock_name': '',
                'lock_wait_time': 0,
                'lock_time': 0,
                'dbpid': 0
            }
            
            for key, default in defaults.items():
                if key not in result:
                    result[key] = default
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return None
    
    def insert_batch(self):
        """Вставка батча в ClickHouse"""
        if not self.batch:
            return
        
        try:
            data = []
            for record in self.batch:
                row = [
                    record['event_date'],
                    record['event_hour'],
                    record['event_minute'],
                    record['event_datetime'],
                    record['event_type'],
                    record['session'],
                    record['transaction'],
                    record['user'][:100],
                    record['process'][:50],
                    record['table_name'][:200],
                    record['lock_type'][:20],
                    record['lock_mode'][:20],
                    record['lock_name'][:200],
                    record['lock_wait_time'],
                    record['lock_time'],
                    record['dbpid'],
                    ''  # raw_line
                ]
                data.append(row)
            
            self.client.execute(
                """
                INSERT INTO lock_events (
                    event_date, event_hour, event_minute, event_datetime,
                    event_type, session_id, transaction_id, user_name,
                    process_name, table_name, lock_type, lock_mode,
                    lock_name, lock_wait_time, lock_time, dbpid, raw_line
                ) VALUES
                """,
                data
            )
            
            logger.debug(f"Вставлено {len(self.batch)} записей о блокировках")
            self.batch = []
            
        except Exception as e:
            logger.error(f"Ошибка вставки: {e}")
            self.batch = []  # очищаем, чтобы не копились
    
    def process_file(self, file_path: str):
        """Обработка файла техжурнала"""
        logger.info(f"Обработка файла: {file_path}")
        
        open_func = gzip.open if file_path.endswith('.gz') else open
        mode = 'rt' if file_path.endswith('.gz') else 'r'
        
        lines_processed = 0
        locks_found = 0
        
        with open_func(file_path, mode, encoding='utf-8', errors='ignore') as f:
            for line in f:
                lines_processed += 1
                
                parsed = self.parse_line(line)
                if parsed:
                    locks_found += 1
                    self.batch.append(parsed)
                    
                    if len(self.batch) >= self.batch_size:
                        self.insert_batch()
                
                if lines_processed % 100000 == 0:
                    logger.info(f"  Обработано {lines_processed} строк, найдено {locks_found} блокировок")
        
        # Вставляем остаток
        if self.batch:
            self.insert_batch()
        
        logger.info(f"Файл обработан: {locks_found} блокировок из {lines_processed} строк")
        return locks_found

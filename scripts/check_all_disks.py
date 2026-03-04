#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Запуск прогноза для всех отслеживаемых дисков
"""

import os
import sys
import logging
from dotenv import load_dotenv
from predict_disk import DiskPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('check_all_disks')

load_dotenv()

def main():
    disks = os.getenv('MONITORED_DISKS', 'C:,D:,E:').split(',')
    disks = [d.strip() for d in disks]
    
    logger.info(f"Запуск прогноза для дисков: {disks}")
    
    results = []
    for disk in disks:
        try:
            predictor = DiskPredictor(disk_letter=disk)
            result = predictor.run()
            results.append(result)
        except Exception as e:
            logger.error(f"Ошибка при обработке диска {disk}: {e}")
    
    # Формируем сводку
    logger.info("\n" + "=" * 60)
    logger.info("СВОДКА ПО ВСЕМ ДИСКАМ")
    logger.info("=" * 60)
    
    for r in results:
        status_emoji = {
            'critical': '🔴',
            'warning': '🟡',
            'normal': '🟢'
        }.get(r['status'], '⚪')
        
        logger.info(f"{status_emoji} {r['disk_letter']}: {r['current_usage']:.1f} ГБ, "
                   f"осталось {r['days_to_limit']:.0f} дней")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()

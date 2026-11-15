# -*- coding: utf-8 -*-
"""
===================================
平台适配器模块
===================================

包含各平台的 Webhook 处理和消息解析逻辑。
"""

from bot.platforms.base import BotPlatform

# 所有可用平台（Webhook 模式）。
# 中国专用平台已按 ADR-0001 删除；Telegram / Discord 的注册由后续 issue 接入，
# 在此之前 handle_webhook 对任何平台都会返回“未知平台”。
ALL_PLATFORMS = {}

__all__ = [
    'BotPlatform',
    'ALL_PLATFORMS',
]

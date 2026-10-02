"""炭窑焖烧志业务规则。

抽屉（前端提示）与后台写入共用本模块的同一条边界、同一句中文，
避免两处各自校验产生漂移。
"""

from __future__ import annotations

import math

from charclamp.domain.models import BurnShift, Clamp

# 既有出炭下限：最近一班峰值温度达到该值才允许出炭
MIN_PEAK_TEMP_FOR_DRAWN = 400.0

# 登记班次时，峰值温度若填写必须大于 0（抽屉与后台同一句）
PEAK_POSITIVE_MSG = "峰值温度若填写须大于 0"
# 重复出炭（并发下的落败方也看到这一句）
ALREADY_DRAWN_MSG = "该窑已出炭，不能重复标记"
NO_SHIFT_MSG = "该窑尚无焖烧班次，不能标记为已出炭"
PEAK_NOT_MEASURED_MSG = "最近班次尚未记录峰值温度，不能标记为已出炭"


class RuleError(ValueError):
    """业务规则校验失败。message 为可直接展示的中文。"""


def latest_shift_for_clamp(clamp: Clamp) -> BurnShift | None:
    if not clamp.shifts:
        return None
    return max(clamp.shifts, key=lambda s: s.started_at)


def parse_shift_peak_temp(raw: str | None) -> float | None:
    """解析班次表单里的峰值温度。

    空值 → None（未测，允许登记）；已填写则必须是大于 0 的数字，
    否则抛 RuleError（PEAK_POSITIVE_MSG）。抽屉与 /shifts/new 共用。
    """
    if raw is None:
        return None
    text = raw.strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        raise RuleError(PEAK_POSITIVE_MSG) from None
    if not math.isfinite(value) or value <= 0:
        raise RuleError(PEAK_POSITIVE_MSG)
    return value


def _format_temp(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else str(value)


def peak_too_low_msg(value: float) -> str:
    return (
        f"最近班次峰值温度 {_format_temp(value)}℃ 低于 "
        f"{MIN_PEAK_TEMP_FOR_DRAWN:.0f}℃，不能标记为已出炭"
    )


def can_mark_clamp_drawn(clamp: Clamp) -> tuple[bool, str]:
    """
    炭窑转为「已出炭」(drawn) 的前提：
    最近一条焖烧班次的峰值温度已记录，且 >= 400℃。

    返回 (是否允许, 中文原因)。抽屉提示与改窑态接口都取这里的同一句话。
    """
    latest = latest_shift_for_clamp(clamp)
    if latest is None:
        return False, NO_SHIFT_MSG
    if latest.peak_temp_c is None:
        return False, PEAK_NOT_MEASURED_MSG
    if latest.peak_temp_c < MIN_PEAK_TEMP_FOR_DRAWN:
        return False, peak_too_low_msg(latest.peak_temp_c)
    return True, ""


def assert_can_set_clamp_status(clamp: Clamp, new_status: str) -> None:
    allowed = {Clamp.STATUS_STACKED, Clamp.STATUS_BURNING, Clamp.STATUS_DRAWN}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == Clamp.STATUS_DRAWN:
        # 已出炭的窑不允许重复出炭（两名管理员并发时落败方走这里）
        if clamp.status == Clamp.STATUS_DRAWN:
            raise RuleError(ALREADY_DRAWN_MSG)
        ok, msg = can_mark_clamp_drawn(clamp)
        if not ok:
            raise RuleError(msg)

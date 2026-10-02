"""炭窑焖烧志业务规则。"""

from __future__ import annotations

from charclamp.domain.models import BurnShift, Clamp

MIN_PEAK_TEMP_FOR_DRAWN = 400.0
# 峰值温度的登记边界：允许不填；一旦填写必须大于 0℃。
# 抽屉前端与后台写入共用这一套边界（见 validate_shift_peak_temp）。
MIN_RECORDED_PEAK_TEMP = 0.0
PEAK_TEMP_MUST_BE_POSITIVE_MSG = "峰值温度若填写须大于 0℃，不能写入时间轴"
ALREADY_DRAWN_MSG = "该窑已标记为已出炭，不能重复标记"


class RuleError(ValueError):
    """业务规则校验失败。"""


def latest_shift_for_clamp(clamp: Clamp) -> BurnShift | None:
    if not clamp.shifts:
        return None
    return max(clamp.shifts, key=lambda s: s.started_at)


def validate_shift_peak_temp(peak_temp_c: float | None) -> None:
    """
    登记焖烧班次时的峰值边界：
    峰值可留空（未测）；只要填写，就必须大于 0℃。
    抽屉与后台写入都走这里，不允许各写一套。
    """
    if peak_temp_c is not None and peak_temp_c <= MIN_RECORDED_PEAK_TEMP:
        raise RuleError(PEAK_TEMP_MUST_BE_POSITIVE_MSG)


def can_mark_clamp_drawn(clamp: Clamp) -> tuple[bool, str]:
    """
    炭窑转为「已出炭」(drawn) 的前提：
    最近一条焖烧班次的峰值温度已记录，且 >= 400℃。
    """
    latest = latest_shift_for_clamp(clamp)
    if latest is None:
        return False, "该窑尚无焖烧班次，不能标记为已出炭"
    if latest.peak_temp_c is None:
        return False, "最近班次尚未记录峰值温度，不能标记为已出炭"
    if latest.peak_temp_c < MIN_PEAK_TEMP_FOR_DRAWN:
        return (
            False,
            f"最近班次峰值温度 {latest.peak_temp_c}℃ 低于 {MIN_PEAK_TEMP_FOR_DRAWN:.0f}℃，不能标记为已出炭",
        )
    return True, ""


def assert_can_set_clamp_status(clamp: Clamp, new_status: str) -> None:
    allowed = {Clamp.STATUS_STACKED, Clamp.STATUS_BURNING, Clamp.STATUS_DRAWN}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == Clamp.STATUS_DRAWN:
        # 并发下另一笔事务可能已把窑标记为已出炭（行锁释放后读到最新状态）。
        if clamp.status == Clamp.STATUS_DRAWN:
            raise RuleError(ALREADY_DRAWN_MSG)
        ok, msg = can_mark_clamp_drawn(clamp)
        if not ok:
            raise RuleError(msg)

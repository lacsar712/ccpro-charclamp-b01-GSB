from __future__ import annotations

from datetime import timedelta

from charclamp.domain.models import BurnShift, Clamp, Site, User, utcnow
from charclamp.infra.db import SyncSessionLocal
from charclamp.infra.security import hash_password


def seed_demo() -> None:
    with SyncSessionLocal() as session:
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            admin = User(username="admin", role="admin", password_hash=hash_password("123456"))
            session.add(admin)
        else:
            admin.password_hash = hash_password("123456")
            admin.role = "admin"

        worker = session.query(User).filter_by(username="worker").first()
        if not worker:
            worker = User(username="worker", role="worker", password_hash=hash_password("123456"))
            session.add(worker)
        else:
            worker.password_hash = hash_password("123456")
            worker.role = "worker"

        # 第二名管理员：与 admin 几乎同时点同一口窑的出炭时，只许一笔成功
        admin2 = session.query(User).filter_by(username="admin2").first()
        if not admin2:
            admin2 = User(username="admin2", role="admin", password_hash=hash_password("123456"))
            session.add(admin2)
        else:
            admin2.password_hash = hash_password("123456")
            admin2.role = "admin"

        if session.query(Site).first():
            session.commit()
            return

        site = Site(name="乌石岗焖烧坞", location="河谷台地北侧", notes="青冈为主，夜班闷窑")
        session.add(site)
        session.flush()

        # 恰好一口「焖烧中」窑：最近一班峰值 455℃ 已达标，可直接演示并发点出炭
        c1 = Clamp(site=site, code="坞东-甲", status=Clamp.STATUS_BURNING, wood_species="青冈")
        # 已码窑：尚未点火、没有任何班次
        c2 = Clamp(site=site, code="坞东-乙", status=Clamp.STATUS_STACKED, wood_species="松木")
        c3 = Clamp(site=site, code="河沿-丙", status=Clamp.STATUS_DRAWN, wood_species="栎木")
        session.add_all([c1, c2, c3])
        session.flush()

        now = utcnow()
        session.add_all(
            [
                BurnShift(
                    clamp=c1,
                    started_at=now - timedelta(hours=10),
                    peak_temp_c=455.0,
                    charcoal_grade="A",
                    notes="峰值已过，可出炭",
                ),
                BurnShift(
                    clamp=c3,
                    started_at=now - timedelta(days=2),
                    peak_temp_c=520.0,
                    charcoal_grade="A+",
                    notes="已出炭班次",
                ),
            ]
        )
        session.commit()

"""一次性迁移：把 user_holdings 从「按 user_id」改为「按 portfolio_id」。

- 新建 portfolios 表（若无）。
- 为每个已有持仓的 user_id 建一个默认实盘「我的实盘」。
- 重建 user_holdings（加 portfolio_id 列 + UNIQUE(portfolio_id, fund_code)），
  把旧行迁到对应用户的默认实盘。

幂等：若 user_holdings 已含 portfolio_id 列则跳过重建。运行：
    ./backend/venv/bin/python3 backend/migrate_portfolios.py
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "data.db")


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 1. portfolios 表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            preset_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS ix_portfolios_user ON portfolios (user_id)")

    # 2. 检查 user_holdings 是否已迁移
    cols = [r[1] for r in cur.execute("PRAGMA table_info(user_holdings)")]
    if not cols:
        print("user_holdings 表不存在，无需迁移（应用启动会按新 schema 建表）。")
        conn.commit()
        conn.close()
        return
    if "portfolio_id" in cols:
        print("user_holdings 已含 portfolio_id，跳过重建。")
        conn.commit()
        conn.close()
        return

    # 3. 为每个有持仓的 user_id 建默认实盘
    users = [r[0] for r in cur.execute("SELECT DISTINCT user_id FROM user_holdings")]
    user_to_pf = {}
    for u in users:
        cur.execute(
            "INSERT INTO portfolios (user_id, name) VALUES (?, ?)", (u, "我的实盘")
        )
        user_to_pf[u] = cur.lastrowid
        print(f"用户 {u} → 默认实盘 id={cur.lastrowid}")

    # 4. 重建 user_holdings
    old_rows = cur.execute(
        "SELECT user_id, fund_code, fund_name, market_value, cost, updated_at FROM user_holdings"
    ).fetchall()

    cur.execute("ALTER TABLE user_holdings RENAME TO user_holdings_old")
    cur.execute(
        """
        CREATE TABLE user_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            fund_name TEXT DEFAULT '',
            market_value REAL NOT NULL DEFAULT 0,
            cost REAL,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE (portfolio_id, fund_code)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_holdings_portfolio ON user_holdings (portfolio_id)"
    )

    for user_id, code, name, mv, cost, updated_at in old_rows:
        pid = user_to_pf[user_id]
        cur.execute(
            """INSERT INTO user_holdings
               (portfolio_id, user_id, fund_code, fund_name, market_value, cost, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, user_id, code, name, mv, cost, updated_at),
        )

    cur.execute("DROP TABLE user_holdings_old")
    conn.commit()
    print(f"迁移完成：{len(old_rows)} 条持仓 → {len(users)} 个默认实盘。")
    conn.close()


if __name__ == "__main__":
    main()

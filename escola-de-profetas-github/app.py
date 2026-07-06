from __future__ import annotations

import csv
import io
import math
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mentoria.db"
PROTECTED_MEDIA_DIR = BASE_DIR / "protected_media"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

app = Flask(__name__)
app.config["SECRET_KEY"] = "mentoria-profetica-prototipo-local"
app.config["WEBHOOK_TOKEN"] = "webhook-prototipo-local"
app.config["AUTO_LOGIN_ADMIN"] = os.environ.get("AUTO_LOGIN_ADMIN", "0").lower() in {"1", "true", "yes", "on"}
app.config["PUBLIC_TEST_ACCESS"] = os.environ.get("PUBLIC_TEST_ACCESS", "1").lower() in {"1", "true", "yes", "on"}


def now() -> datetime:
    return datetime.now()


def now_str() -> str:
    return now().strftime(DATE_FORMAT)


def parse_dt(value: str | None) -> datetime:
    if not value:
        return now()
    return datetime.strptime(value, DATE_FORMAT)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def execute(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur


def init_db() -> None:
    with app.app_context():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                password TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                role TEXT NOT NULL DEFAULT 'user',
                spiritual_profile TEXT,
                subscription_started_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                last_seen_at TEXT,
                current_page TEXT
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                subtitle TEXT,
                description TEXT NOT NULL,
                product_type TEXT NOT NULL DEFAULT 'curso',
                price_label TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                price_cents INTEGER,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payment_provider TEXT,
                payment_reference TEXT,
                amount_cents INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                confirmed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(course_id) REFERENCES courses(id)
            );

            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, course_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(course_id) REFERENCES courses(id)
            );

            CREATE TABLE IF NOT EXISTS user_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'interesse',
                acquired_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                notes TEXT,
                UNIQUE(user_id, product_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'aguardando_pagamento',
                amount_label TEXT,
                checkout_reference TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS course_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cycle_slug TEXT NOT NULL,
                content_slug TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, cycle_slug, content_slug),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS course_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cycle_slug TEXT NOT NULL,
                content_slug TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'nao_iniciado',
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, cycle_slug, content_slug),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS content_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trail TEXT NOT NULL,
                week_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT,
                content_type TEXT NOT NULL,
                body TEXT NOT NULL,
                verse TEXT,
                is_premium INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'bloqueado',
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, content_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(content_id) REFERENCES content_items(id)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                page TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS questions_channel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'nova',
                is_sensitive INTEGER NOT NULL DEFAULT 0,
                share_anonymous INTEGER NOT NULL DEFAULT 0,
                answer TEXT,
                created_at TEXT NOT NULL,
                answered_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS prayer_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                request TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                mentor_reply TEXT,
                created_at TEXT NOT NULL,
                replied_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                mood TEXT,
                share_with_mentor INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS spiritual_stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT NOT NULL,
                description TEXT NOT NULL,
                station_order INTEGER NOT NULL,
                theme_color TEXT,
                icon_name TEXT,
                spiritual_phrase TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS station_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER NOT NULL,
                lesson_order INTEGER NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT,
                audio_url TEXT,
                audio_duration TEXT,
                lesson_text TEXT NOT NULL,
                exercise_title TEXT NOT NULL,
                exercise_text TEXT NOT NULL,
                exercise_prompt TEXT NOT NULL,
                required_reflection_min_chars INTEGER NOT NULL DEFAULT 80,
                created_at TEXT NOT NULL,
                UNIQUE(station_id, lesson_order),
                FOREIGN KEY(station_id) REFERENCES spiritual_stations(id)
            );

            CREATE TABLE IF NOT EXISTS user_station_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                station_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'bloqueada',
                percent_complete INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, station_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(station_id) REFERENCES spiritual_stations(id)
            );

            CREATE TABLE IF NOT EXISTS user_lesson_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'bloqueada',
                listened_at TEXT,
                exercise_answer TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, lesson_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(lesson_id) REFERENCES station_lessons(id)
            );

            CREATE TABLE IF NOT EXISTS station_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                station_id INTEGER,
                lesson_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(station_id) REFERENCES spiritual_stations(id),
                FOREIGN KEY(lesson_id) REFERENCES station_lessons(id)
            );

            CREATE TABLE IF NOT EXISTS user_presence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                last_seen_at TEXT NOT NULL,
                current_page TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            """
        )
        db.commit()
        migrate_course_tables()
        seed_courses()
        if query_one("SELECT id FROM users LIMIT 1") is None:
            seed_db()
        seed_admin_user()
        seed_products()
        sync_legacy_paid_access()
        if query_one("SELECT id FROM spiritual_stations LIMIT 1") is None:
            seed_station_journey()
        initialize_station_progress_for_all_users()


def column_exists(table: str, column: str) -> bool:
    return any(row["name"] == column for row in query_all(f"PRAGMA table_info({table})"))


def migrate_course_tables() -> None:
    if not column_exists("users", "updated_at"):
        execute("ALTER TABLE users ADD COLUMN updated_at TEXT")
    if not column_exists("users", "password"):
        execute("ALTER TABLE users ADD COLUMN password TEXT")
    if not column_exists("course_comments", "course_slug"):
        execute("ALTER TABLE course_comments ADD COLUMN course_slug TEXT NOT NULL DEFAULT 'escola-de-profetas'")
    if not column_exists("course_progress", "course_slug"):
        execute("ALTER TABLE course_progress ADD COLUMN course_slug TEXT NOT NULL DEFAULT 'escola-de-profetas'")


def seed_courses() -> None:
    execute(
        """
        INSERT INTO courses (slug, title, description, price_cents, active, created_at, updated_at)
        VALUES ('escola-de-profetas', 'Escola de Profetas', 'Formação espiritual para voz, visão, caráter e serviço ao Corpo de Cristo.', 1000, 1, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            price_cents = excluded.price_cents,
            active = 1,
            updated_at = excluded.updated_at
        """,
        (now_str(), now_str()),
    )


def seed_admin_user() -> None:
    existing = query_one("SELECT id FROM users WHERE email = ?", ("admin@escoladeprofetas.local",))
    if existing:
        execute("UPDATE users SET role = 'admin', updated_at = COALESCE(created_at, ?) WHERE id = ?", (now_str(), existing["id"]))
        return
    execute(
        """
        INSERT INTO users
        (name, email, password_hash, plan, role, spiritual_profile, subscription_started_at, created_at, last_seen_at, current_page)
        VALUES (?, ?, ?, 'premium', 'admin', 'maturidade', ?, ?, ?, '/admin')
        """,
        (
            "Admin Escola",
            "admin@escoladeprofetas.local",
            generate_password_hash("admin123"),
            now_str(),
            now_str(),
            now_str(),
        ),
    )


def get_course_by_slug(slug: str) -> sqlite3.Row | None:
    return query_one("SELECT * FROM courses WHERE slug = ? AND active = 1", (slug,))


def activate_enrollment(user_id: int, course_id: int) -> None:
    execute(
        """
        INSERT INTO enrollments (user_id, course_id, status, created_at, updated_at)
        VALUES (?, ?, 'active', ?, ?)
        ON CONFLICT(user_id, course_id) DO UPDATE SET
            status = 'active',
            updated_at = excluded.updated_at
        """,
        (user_id, course_id, now_str(), now_str()),
    )


def user_has_active_enrollment(user_id: int, course_slug: str) -> bool:
    row = query_one(
        """
        SELECT 1
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        WHERE e.user_id = ?
          AND c.slug = ?
          AND c.active = 1
          AND e.status = 'active'
        LIMIT 1
        """,
        (user_id, course_slug),
    )
    return bool(row)


def get_or_create_pending_purchase(user_id: int, course_id: int) -> sqlite3.Row:
    paid = query_one(
        "SELECT * FROM purchases WHERE user_id = ? AND course_id = ? AND status = 'paid' ORDER BY id DESC LIMIT 1",
        (user_id, course_id),
    )
    if paid:
        activate_enrollment(user_id, course_id)
        return paid
    pending = query_one(
        "SELECT * FROM purchases WHERE user_id = ? AND course_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (user_id, course_id),
    )
    if pending:
        return pending
    cur = execute(
        """
        INSERT INTO purchases (user_id, course_id, status, payment_provider, payment_reference, amount_cents, created_at, updated_at)
        VALUES (?, ?, 'pending', 'prototype', ?, (SELECT price_cents FROM courses WHERE id = ?), ?, ?)
        """,
        (user_id, course_id, f"prototype-{course_id}-{user_id}-{int(now().timestamp())}", course_id, now_str(), now_str()),
    )
    return query_one("SELECT * FROM purchases WHERE id = ?", (cur.lastrowid,))


def mark_purchase_paid_by_id(purchase_id: int, payment_reference: str | None = None) -> sqlite3.Row | None:
    purchase = query_one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))
    if not purchase:
        return None
    execute(
        """
        UPDATE purchases
        SET status = 'paid',
            payment_reference = COALESCE(?, payment_reference),
            confirmed_at = COALESCE(confirmed_at, ?),
            updated_at = ?
        WHERE id = ?
        """,
        (payment_reference, now_str(), now_str(), purchase_id),
    )
    activate_enrollment(purchase["user_id"], purchase["course_id"])
    return query_one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))


def get_user_courses(user_id: int) -> list[sqlite3.Row]:
    return query_all(
        """
        SELECT c.*, e.status AS enrollment_status, e.updated_at AS enrollment_updated_at
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        WHERE e.user_id = ? AND e.status = 'active' AND c.active = 1
        ORDER BY e.updated_at DESC
        """,
        (user_id,),
    )


def sync_legacy_paid_access() -> None:
    course = get_course_by_slug("escola-de-profetas")
    if not course:
        return
    rows = query_all(
        """
        SELECT DISTINCT up.user_id
        FROM user_products up
        JOIN products p ON p.id = up.product_id
        WHERE p.slug = 'escola-de-profetas' AND up.status IN ('ativo', 'pago', 'aprovado')
        """
    )
    for row in rows:
        activate_enrollment(row["user_id"], course["id"])


def seed_db() -> None:
    start_6_months = now() - timedelta(days=183)
    users = [
        ("Ana Free", "free@mentoria.local", "free", "user", "reconexao", None),
        ("Beatriz Premium", "premium@mentoria.local", "premium", "user", "discernimento", start_6_months.strftime(DATE_FORMAT)),
        ("Admin Escola", "admin@mentoria.local", "premium", "admin", "maturidade", start_6_months.strftime(DATE_FORMAT)),
    ]
    for name, email, plan, role, profile, started_at in users:
        execute(
            """
            INSERT INTO users
            (name, email, password_hash, plan, role, spiritual_profile, subscription_started_at, created_at, last_seen_at, current_page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                generate_password_hash("demo123"),
                plan,
                role,
                profile,
                started_at,
                now_str(),
                now_str(),
                "/minha-jornada",
            ),
        )

    free_items = [
        ("Fundamentos", 1, "Recomeçar com Deus", "Um devocional para voltar ao centro.", "devocional", "Jesus não chama você para pressa, mas para permanência. Comece com uma oração simples e a Palavra aberta.", "João 15:5", 0),
        ("Fundamentos", 1, "Oração de Entrega", "Uma oração curta para alinhar o coração.", "oração", "Senhor, guia meus passos com sabedoria, humildade e amor pela tua Palavra.", "Salmo 25:4", 0),
        ("Fundamentos", 2, "Discernir sem Medo", "Paz, Palavra e maturidade.", "aula", "Discernimento bíblico cresce quando a vida se rende a Cristo e aprende a testar tudo pela Palavra.", "1 João 4:1", 0),
        ("Fundamentos", 2, "Diário de Gratidão", "Registro simples da semana.", "desafio", "Anote três sinais de cuidado de Deus percebidos nesta semana.", "1 Tessalonicenses 5:18", 0),
    ]
    premium_items = [
        ("Plano Crescer", 1, "Semana 1: Raiz em Cristo", "A base antes do movimento.", "devocional", "Toda jornada espiritual saudável começa em Cristo, não em desempenho. Ore, leia e caminhe com constância.", "Colossenses 2:7", 1),
        ("Plano Crescer", 1, "Check-in da Semana 1", "Perceba seu ritmo espiritual.", "checkin", "Como esteve sua vida de oração nesta semana? Responda com honestidade e graça.", "Mateus 6:6", 1),
        ("Plano Crescer", 2, "Paz para Decidir", "Ansiedade entregue em oração.", "aula", "Decisões maduras nascem de paz, conselho, Palavra e tempo. Deus não precisa ser apressado.", "Filipenses 4:6-7", 1),
        ("Plano Crescer", 3, "Discernimento Bíblico", "Testar, guardar e amadurecer.", "devocional", "Nem toda impressão deve governar sua vida. Discernimento honra a Escritura e os frutos.", "Hebreus 5:14", 1),
        ("Plano Crescer", 4, "Oração Intercessora", "Cuidado sem peso excessivo.", "oração", "Interceder e carregar culpa são coisas diferentes. Entregue pessoas a Deus com amor e limite santo.", "1 Timóteo 2:1", 1),
        ("Plano Crescer", 5, "Chamado e Serviço", "Antes de título, fruto.", "aula", "O chamado amadurece no serviço fiel, na submissão a Cristo e na confirmação prática.", "Efésios 4:12", 1),
        ("Plano Crescer", 6, "Anjos sob Governo de Deus", "Segurança bíblica e reverência.", "aula", "Anjos são servos de Deus. A adoração, oração e confiança pertencem ao Senhor.", "Hebreus 1:14", 1),
        ("Plano Crescer", 7, "Proteção Espiritual", "Vigilância com sobriedade.", "devocional", "A armadura de Deus aponta para verdade, justiça, fé, salvação e Palavra. Caminhe com sobriedade.", "Efésios 6:11", 1),
        ("Plano Crescer", 8, "Maturidade Emocional", "Graça também forma afetos.", "desafio", "Nomeie sentimentos, ore com sinceridade e procure apoio quando necessário.", "Salmo 139:23", 1),
        ("Plano Crescer", 9, "Dons com Amor", "Dom sem amor perde o caminho.", "aula", "Dons espirituais existem para edificação, serviço e glória de Deus.", "1 Coríntios 13:1", 1),
        ("Plano Crescer", 10, "Rotina Devocional", "Constância possível.", "desafio", "Escolha um horário realista para Palavra, oração e silêncio diante de Deus.", "Salmo 1:2", 1),
        ("Plano Crescer", 11, "Frutos Práticos", "O invisível aparece no cotidiano.", "checkin", "Que fruto do Espírito você percebe crescendo? Onde precisa de cuidado?", "Gálatas 5:22-23", 1),
        ("Plano Crescer", 12, "Revisão da Jornada", "Olhar para trás com gratidão.", "questionario", "Revise aprendizados, dúvidas e próximos passos em oração.", "Filipenses 1:6", 1),
    ]
    for item in free_items + premium_items:
        execute(
            """
            INSERT INTO content_items
            (trail, week_number, title, subtitle, content_type, body, verse, is_premium, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*item, now_str()),
        )

    premium_user = query_one("SELECT id FROM users WHERE email = ?", ("premium@mentoria.local",))
    free_user = query_one("SELECT id FROM users WHERE email = ?", ("free@mentoria.local",))
    if premium_user:
        for item in query_all("SELECT id, week_number FROM content_items WHERE week_number <= 3"):
            execute(
                "INSERT INTO user_progress (user_id, content_id, status, completed_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (premium_user["id"], item["id"], "concluido" if item["week_number"] <= 2 else "iniciado", now_str() if item["week_number"] <= 2 else None, now_str()),
            )
    if free_user:
        for item in query_all("SELECT id FROM content_items WHERE is_premium = 0 LIMIT 2"):
            execute(
                "INSERT INTO user_progress (user_id, content_id, status, completed_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (free_user["id"], item["id"], "concluido", now_str(), now_str()),
            )

    execute(
        "INSERT INTO questions_channel (user_id, category, question, status, is_sensitive, share_anonymous, answer, created_at, answered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (premium_user["id"], "Discernimento", "Como diferenciar medo de direção de Deus?", "respondida", 0, 1, "Observe se a direção se alinha à Palavra, produz fruto de paz e pode ser confirmada por conselhos maduros.", now_str(), now_str()),
    )
    execute(
        "INSERT INTO prayer_requests (user_id, category, request, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (premium_user["id"], "Vida emocional", "Preciso de oração por ansiedade e decisões familiares.", "pendente", now_str()),
    )
    execute(
        "INSERT INTO journal_entries (user_id, title, content, mood, share_with_mentor, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (premium_user["id"], "Semana intensa", "Tenho sentido medo, mas quero permanecer firme em Deus.", "sensivel", 1, now_str()),
    )
    execute(
        "INSERT INTO activity_log (user_id, action, page, created_at) VALUES (?, ?, ?, ?)",
        (premium_user["id"], "abriu pagina", "/minha-jornada", now_str()),
    )


def product_seed_data() -> list[dict[str, str]]:
    return [
        {
            "slug": "escola-de-profetas",
            "name": "Escola de Profetas",
            "subtitle": "Formação espiritual para voz, visão, caráter e serviço.",
            "description": "Produto principal da formação profética, com ciclos, jornada, conteúdos e acompanhamento espiritual.",
            "product_type": "formacao",
            "price_label": "Produto principal",
        },
        {
            "slug": "como-trabalhar-com-os-anjos",
            "name": "Como ministrar com os anjos",
            "subtitle": "Ensino bíblico, reverente e seguro.",
            "description": "Conteúdo sobre anjos como servos de Deus, sem culto, invocação ou comandos, com Cristo no centro.",
            "product_type": "curso-extra",
            "price_label": "Produto adicional",
        },
        {
            "slug": "implantacao-de-ministerios-profeticos",
            "name": "Implantação de Ministérios Proféticos",
            "subtitle": "Fundamentos, governo, maturidade e cuidado.",
            "description": "Trilha para organizar ministérios proféticos com base bíblica, caráter, liderança e serviço ao Corpo de Cristo.",
            "product_type": "curso-extra",
            "price_label": "Produto adicional",
        },
        {
            "slug": "como-montar-uma-sala-profetica",
            "name": "Como montar uma sala profética",
            "subtitle": "Ambiente, equipe, fluxo e discernimento.",
            "description": "Material prático para estruturar uma sala profética com responsabilidade pastoral, ordem e maturidade espiritual.",
            "product_type": "curso-extra",
            "price_label": "Produto adicional",
        },
        {
            "slug": "como-montar-uma-sala-de-oracao-por-cura",
            "name": "Como montar uma sala de oração por cura",
            "subtitle": "Oração, acolhimento e cuidado integral.",
            "description": "Direção para estruturar uma sala de oração por cura com ética, prudência e orientação para apoio pastoral/profissional quando necessário.",
            "product_type": "curso-extra",
            "price_label": "Produto adicional",
        },
    ]


def seed_products() -> None:
    for product in product_seed_data():
        execute(
            """
            INSERT INTO products (slug, name, subtitle, description, product_type, price_label, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                subtitle = excluded.subtitle,
                description = excluded.description,
                product_type = excluded.product_type,
                price_label = excluded.price_label,
                is_active = 1
            """,
            (
                product["slug"],
                product["name"],
                product["subtitle"],
                product["description"],
                product["product_type"],
                product["price_label"],
                now_str(),
            ),
        )
    main_product = query_one("SELECT id FROM products WHERE slug = ?", ("escola-de-profetas",))
    if not main_product:
        return
    for user in query_all("SELECT id FROM users"):
        execute(
            """
            INSERT OR IGNORE INTO user_products
            (user_id, product_id, status, acquired_at, created_at, updated_at, notes)
            VALUES (?, ?, 'ativo', ?, ?, ?, ?)
            """,
            (user["id"], main_product["id"], now_str(), now_str(), now_str(), "Produto principal da Escola."),
        )


def assign_user_product(user_id: int, product_slug: str, status: str = "interesse", notes: str | None = None) -> None:
    product = query_one("SELECT id FROM products WHERE slug = ?", (product_slug,))
    if not product:
        return
    acquired_at = now_str() if status == "ativo" else None
    execute(
        """
        INSERT INTO user_products
        (user_id, product_id, status, acquired_at, created_at, updated_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, product_id) DO UPDATE SET
            status = excluded.status,
            acquired_at = COALESCE(user_products.acquired_at, excluded.acquired_at),
            updated_at = excluded.updated_at,
            notes = excluded.notes
        """,
        (user_id, product["id"], status, acquired_at, now_str(), now_str(), notes),
    )


def confirmed_user_products(user_id: int) -> list[sqlite3.Row]:
    return query_all(
        """
        SELECT p.*, up.status AS access_status, up.acquired_at, up.updated_at AS access_updated_at
        FROM user_products up
        JOIN products p ON p.id = up.product_id
        WHERE up.user_id = ?
          AND p.is_active = 1
          AND up.status IN ('ativo', 'pago', 'aprovado')
        ORDER BY COALESCE(up.acquired_at, up.updated_at) DESC, p.id
        """,
        (user_id,),
    )


def has_confirmed_product(user_id: int, product_slug: str) -> bool:
    if user_has_active_enrollment(user_id, product_slug):
        return True
    row = query_one(
        """
        SELECT 1
        FROM user_products up
        JOIN products p ON p.id = up.product_id
        WHERE up.user_id = ?
          AND p.slug = ?
          AND p.is_active = 1
          AND up.status IN ('ativo', 'pago', 'aprovado')
        LIMIT 1
        """,
        (user_id, product_slug),
    )
    return bool(row)


def station_seed_data() -> list[dict[str, Any]]:
    return [
        {
            "slug": "filiacao",
            "title": "Filiação",
            "subtitle": "Identidade antes de desempenho",
            "description": "Eu sou filha/filho de Deus antes de fazer qualquer coisa para Deus.",
            "phrase": "Antes de servir, aprenda a permanecer como filha diante do Pai.",
            "icon": "crown",
            "lessons": [
                ("Deus começa pelo amor, não pela cobrança.", "Receber amor antes de tentar merecer.", "Escrever como você se sente sendo chamada de filha/filho de Deus."),
                ("Descansando da performance espiritual.", "Valor não nasce de desempenho religioso.", "Identificar onde você tem tentado provar valor."),
                ("Permanecer antes de produzir.", "A presença forma antes dos frutos.", "Orar 5 minutos sem pedir nada, apenas permanecendo."),
            ],
        },
        {
            "slug": "intimidade",
            "title": "Intimidade",
            "subtitle": "Vida secreta, oração e escuta",
            "description": "Vida secreta, oração, escuta e relacionamento com Deus.",
            "phrase": "A intimidade forma raízes antes que os frutos apareçam.",
            "icon": "lamp",
            "lessons": [
                ("O secreto como lugar de formação.", "O Pai forma o coração longe da pressa.", "Separar um horário simples de oração."),
                ("Como ouvir a voz de Deus com maturidade.", "Escuta bíblica, paz e sobriedade.", "Silenciar, ler um versículo e registrar uma percepção."),
                ("Diário espiritual como ferramenta de escuta.", "Registrar ajuda a perceber caminhos.", "Registrar uma oração e uma resposta prática."),
            ],
        },
        {
            "slug": "cura-interior",
            "title": "Cura Interior",
            "subtitle": "Deus cuidando das raízes",
            "description": "Deus tratando feridas, ansiedade, culpa, rejeição e comparação.",
            "phrase": "Deus não quer apenas usar você; Ele também quer cuidar de você.",
            "icon": "heart",
            "lessons": [
                ("Deus trata a raiz, não apenas o comportamento.", "Cuidado profundo com verdade e graça.", "Nomear uma ferida ou medo que precisa ser entregue."),
                ("Perdão como caminho de liberdade.", "Perdoar sem negar processos e limites.", "Escrever uma oração de entrega."),
                ("Identidade curada não vive de comparação.", "Trocar comparação por verdade bíblica.", "Identificar uma comparação e trocar por uma verdade bíblica."),
            ],
        },
        {
            "slug": "discernimento",
            "title": "Discernimento",
            "subtitle": "Direção, paz e maturidade",
            "description": "Como ouvir a voz de Deus, discernir direção, paz, ansiedade, impressões e ambientes espirituais.",
            "phrase": "Discernimento não é pressa por respostas; é maturidade para reconhecer a direção de Deus.",
            "icon": "compass",
            "lessons": [
                ("Voz de Deus, ansiedade ou desejo?", "Separar impulso, medo e direção.", "Separar uma situação em desejo, medo e possível direção."),
                ("A Palavra como filtro da escuta.", "Toda percepção precisa honrar a Escritura.", "Confrontar uma percepção com um princípio bíblico."),
                ("Paz, frutos e confirmação.", "Direção madura produz bons frutos.", "Avaliar se uma direção produz paz, humildade e obediência."),
            ],
        },
        {
            "slug": "obediencia-frutos",
            "title": "Obediência e Frutos",
            "subtitle": "Constância que amadurece",
            "description": "Responder a Deus com prática, constância, frutos do Espírito e fidelidade.",
            "phrase": "A voz de Deus amadurece em nós quando respondemos com obediência.",
            "icon": "seedling",
            "lessons": [
                ("Obedecer no simples.", "O sim pequeno também forma maturidade.", "Escolher uma pequena obediência para hoje."),
                ("Frutos antes de sinais.", "Caráter sustenta qualquer dom.", "Avaliar qual fruto do Espírito precisa amadurecer."),
                ("Constância quando não há emoção.", "Fidelidade também cresce no cotidiano.", "Criar um compromisso devocional de 7 dias."),
            ],
        },
        {
            "slug": "chamado-dons",
            "title": "Chamado e Dons",
            "subtitle": "Serviço, identidade e maturidade",
            "description": "Chamado, dons de governo, serviço, identidade ministerial e maturidade.",
            "phrase": "Chamado não começa no palco; começa no serviço fiel.",
            "icon": "flame",
            "lessons": [
                ("Chamado não é título, é serviço.", "O chamado aparece no amor prático.", "Escrever onde você já serve naturalmente."),
                ("Dons de governo e maturidade.", "Perceber tendências sem absolutizar títulos.", "Refletir sobre Pastor, Apóstolo, Mestre, Profeta e Evangelista."),
                ("Como amadurecer um dom sem vaidade.", "Dom precisa caminhar com caráter.", "Identificar um dom e uma área de caráter a amadurecer."),
            ],
        },
        {
            "slug": "servico-corpo",
            "title": "Serviço ao Corpo de Cristo",
            "subtitle": "Amor que edifica pessoas",
            "description": "Servir pessoas com amor, humildade, responsabilidade, maturidade e edificação do Corpo.",
            "phrase": "O verdadeiro crescimento espiritual nos conduz ao amor, ao serviço e à edificação do Corpo.",
            "icon": "hands",
            "lessons": [
                ("O Corpo de Cristo precisa de membros saudáveis.", "Servir melhor começa em permanecer saudável.", "Escrever como você pode edificar pessoas."),
                ("Servir sem se esgotar.", "Limites também protegem o amor.", "Identificar limites saudáveis no serviço."),
                ("Amor, humildade e responsabilidade.", "Serviço maduro tem fruto e cuidado.", "Criar um plano simples de serviço para os próximos 30 dias."),
            ],
        },
    ]


FORMATION_CYCLES: list[dict[str, Any]] = [
    {
        "slug": "leao",
        "name": "Leão",
        "symbol": "♜",
        "title": "Governo e Identidade",
        "phrase": "Antes de governar ambientes, Deus forma identidade.",
        "modules": ["filiacao", "chamado-dons"],
    },
    {
        "slug": "aguia",
        "name": "Águia",
        "symbol": "△",
        "title": "Visão e Discernimento",
        "phrase": "Quem aprende a subir em Deus enxerga além da pressão do momento.",
        "modules": ["intimidade", "discernimento"],
    },
    {
        "slug": "homem",
        "name": "Homem",
        "symbol": "◇",
        "title": "Caráter e Maturidade",
        "phrase": "O profético amadurece quando o caráter sustenta a sensibilidade.",
        "modules": ["cura-interior", "obediencia-frutos"],
    },
    {
        "slug": "boi",
        "name": "Boi",
        "symbol": "□",
        "title": "Serviço e Constância",
        "phrase": "O chamado se confirma no amor que serve.",
        "modules": ["servico-corpo"],
    },
]


COURSE_CYCLES: dict[str, dict[str, Any]] = {
    "leao": {
        "slug": "leao",
        "name": "Leão",
        "title": "Governo e Identidade",
        "description": "Identidade, filiação, autoridade, chamado e dons.",
        "phrase": "Antes de governar ambientes, Deus forma identidade.",
        "contents": [
            {
                "slug": "filiacao-antes-de-funcao",
                "title": "Filiação antes de função",
                "description": "Antes de servir, liderar ou exercer qualquer dom, o aluno precisa compreender sua identidade como filho ou filha de Deus.",
                "video_path": "videos/ciclo_leao_01_filiacao.mp4",
                "pdf_path": "pdfs/ciclo_leao_01_filiacao.pdf",
                "reflection_prompt": "Escreva como você tem se enxergado diante de Deus: como filho amado ou como alguém tentando provar valor?",
                "order": 1,
            },
            {
                "slug": "identidade-profetica-sem-performance",
                "title": "Identidade profética sem performance",
                "description": "O profético não nasce da necessidade de impressionar, mas de uma identidade firmada em Deus.",
                "video_path": "videos/ciclo_leao_02_identidade_sem_performance.mp4",
                "pdf_path": "pdfs/ciclo_leao_02_identidade_sem_performance.pdf",
                "reflection_prompt": "Identifique uma área em que você tem tentado provar valor espiritual e entregue isso a Deus em oração.",
                "order": 2,
            },
            {
                "slug": "autoridade-com-humildade",
                "title": "Autoridade com humildade",
                "description": "Autoridade espiritual madura não é domínio sobre pessoas, mas serviço, responsabilidade e obediência a Deus.",
                "video_path": "videos/ciclo_leao_03_autoridade_humildade.mp4",
                "pdf_path": "pdfs/ciclo_leao_03_autoridade_humildade.pdf",
                "reflection_prompt": "Escreva uma situação em que você precisa exercer autoridade com mais humildade e maturidade.",
                "order": 3,
            },
            {
                "slug": "chamado-e-dons-em-processo",
                "title": "Chamado e dons em processo",
                "description": "Dons precisam ser amadurecidos. Chamado não é título; é formação, serviço e frutos.",
                "video_path": "videos/ciclo_leao_04_chamado_dons.mp4",
                "pdf_path": "pdfs/ciclo_leao_04_chamado_dons.pdf",
                "reflection_prompt": "Quais dons ou inclinações espirituais você percebe em sua vida? Como eles podem amadurecer com caráter?",
                "order": 4,
            },
        ],
    },
    "aguia": {
        "slug": "aguia",
        "name": "Águia",
        "title": "Visão e Discernimento",
        "description": "Intimidade, escuta, discernimento, direção e maturidade profética.",
        "phrase": "Quem aprende a subir em Deus enxerga além da pressão do momento.",
        "contents": [
            {
                "slug": "profetico-nasce-na-presenca",
                "title": "O profético nasce na Presença",
                "description": "Antes de falar em nome de Deus, é preciso aprender a permanecer com Deus.",
                "video_path": "videos/ciclo_aguia_01_profetico_presenca.mp4",
                "pdf_path": "pdfs/ciclo_aguia_01_profetico_presenca.pdf",
                "reflection_prompt": "Separe alguns minutos em silêncio diante de Deus e registre o que percebeu em oração, sem pressa e sem ansiedade.",
                "order": 1,
            },
            {
                "slug": "escuta-espiritual-fundamento-biblico",
                "title": "Escuta espiritual com fundamento bíblico",
                "description": "A voz de Deus nunca contradiz o caráter de Cristo nem os princípios da Palavra.",
                "video_path": "videos/ciclo_aguia_02_escuta_biblica.mp4",
                "pdf_path": "pdfs/ciclo_aguia_02_escuta_biblica.pdf",
                "reflection_prompt": "Escreva uma percepção que você teve em oração e avalie: ela está alinhada à Palavra, produz paz e conduz à obediência?",
                "order": 2,
            },
            {
                "slug": "discernindo-voz-desejo-ansiedade",
                "title": "Discernindo voz, desejo e ansiedade",
                "description": "Discernimento espiritual envolve maturidade para separar direção de Deus, vontade pessoal e pressão emocional.",
                "video_path": "videos/ciclo_aguia_03_discernimento.mp4",
                "pdf_path": "pdfs/ciclo_aguia_03_discernimento.pdf",
                "reflection_prompt": "Escolha uma decisão atual e escreva três colunas: desejo, medo/ansiedade e possível direção de Deus.",
                "order": 3,
            },
            {
                "slug": "visao-espiritual-direcao",
                "title": "Visão espiritual e direção",
                "description": "A visão profética madura não gera confusão, mas clareza, responsabilidade e serviço.",
                "video_path": "videos/ciclo_aguia_04_visao_direcao.mp4",
                "pdf_path": "pdfs/ciclo_aguia_04_visao_direcao.pdf",
                "reflection_prompt": "Escreva qual direção você sente que Deus tem amadurecido em você e qual próximo passo simples pode ser dado.",
                "order": 4,
            },
        ],
    },
    "homem": {
        "slug": "homem",
        "name": "Homem",
        "title": "Caráter e Maturidade",
        "description": "Cura interior, obediência, frutos, caráter e maturidade.",
        "phrase": "O profético amadurece quando o caráter sustenta a sensibilidade.",
        "contents": [
            {
                "slug": "deus-trata-a-raiz",
                "title": "Deus trata a raiz",
                "description": "A formação espiritual não trabalha apenas comportamento, mas raízes internas, feridas, motivações e respostas do coração.",
                "video_path": "videos/ciclo_homem_01_deus_trata_raiz.mp4",
                "pdf_path": "pdfs/ciclo_homem_01_deus_trata_raiz.pdf",
                "reflection_prompt": "Escreva uma área interna que precisa ser tratada por Deus com verdade, graça e maturidade.",
                "order": 1,
            },
            {
                "slug": "cura-interior-identidade-curada",
                "title": "Cura interior e identidade curada",
                "description": "Uma identidade curada aprende a não viver de comparação, rejeição, medo ou necessidade de aprovação.",
                "video_path": "videos/ciclo_homem_02_cura_identidade.mp4",
                "pdf_path": "pdfs/ciclo_homem_02_cura_identidade.pdf",
                "reflection_prompt": "Identifique uma comparação que tem afetado sua caminhada e substitua por uma verdade bíblica sobre quem você é em Deus.",
                "order": 2,
            },
            {
                "slug": "obediencia-no-secreto",
                "title": "Obediência no secreto",
                "description": "O profético amadurece quando a pessoa responde a Deus em pequenas obediências, mesmo quando ninguém vê.",
                "video_path": "videos/ciclo_homem_03_obediencia_secreto.mp4",
                "pdf_path": "pdfs/ciclo_homem_03_obediencia_secreto.pdf",
                "reflection_prompt": "Qual pequena obediência Deus está pedindo de você hoje?",
                "order": 3,
            },
            {
                "slug": "frutos-antes-de-sinais",
                "title": "Frutos antes de sinais",
                "description": "Sinais não substituem frutos. Maturidade espiritual é percebida no amor, domínio próprio, paciência, mansidão e fidelidade.",
                "video_path": "videos/ciclo_homem_04_frutos.mp4",
                "pdf_path": "pdfs/ciclo_homem_04_frutos.pdf",
                "reflection_prompt": "Escolha um fruto do Espírito que precisa amadurecer em sua vida e escreva uma prática concreta para esta semana.",
                "order": 4,
            },
        ],
    },
    "boi": {
        "slug": "boi",
        "name": "Boi",
        "title": "Serviço e Constância",
        "description": "Serviço, constância, edificação, responsabilidade e Corpo de Cristo.",
        "phrase": "O chamado se confirma no amor que serve.",
        "contents": [
            {
                "slug": "chamado-que-serve",
                "title": "Chamado que serve",
                "description": "O chamado não amadurece no desejo de ser visto, mas na disposição de edificar pessoas com amor e responsabilidade.",
                "video_path": "videos/ciclo_boi_01_chamado_serve.mp4",
                "pdf_path": "pdfs/ciclo_boi_01_chamado_serve.pdf",
                "reflection_prompt": "Escreva uma forma prática de servir alguém nesta semana sem buscar reconhecimento.",
                "order": 1,
            },
            {
                "slug": "constancia-sem-esgotamento",
                "title": "Constância sem esgotamento",
                "description": "Servir com maturidade também envolve limites saudáveis, vida com Deus e responsabilidade emocional.",
                "video_path": "videos/ciclo_boi_02_constancia.mp4",
                "pdf_path": "pdfs/ciclo_boi_02_constancia.pdf",
                "reflection_prompt": "Quais limites você precisa respeitar para servir com saúde, alegria e constância?",
                "order": 2,
            },
            {
                "slug": "edificacao-do-corpo-de-cristo",
                "title": "Edificação do Corpo de Cristo",
                "description": "O objetivo da formação profética é edificar o Corpo de Cristo com amor, verdade, humildade e discernimento.",
                "video_path": "videos/ciclo_boi_03_edificacao_corpo.mp4",
                "pdf_path": "pdfs/ciclo_boi_03_edificacao_corpo.pdf",
                "reflection_prompt": "Como sua vida, dons e serviço podem edificar pessoas de forma prática?",
                "order": 3,
            },
            {
                "slug": "enviado-para-servir",
                "title": "Enviado para servir",
                "description": "A jornada não termina no aprendizado. A formação amadurece quando se transforma em serviço fiel e amoroso.",
                "video_path": "videos/ciclo_boi_04_enviado_servir.mp4",
                "pdf_path": "pdfs/ciclo_boi_04_enviado_servir.pdf",
                "reflection_prompt": "Crie um plano simples de serviço para os próximos 30 dias.",
                "order": 4,
            },
        ],
    },
}


def course_cycle_by_slug(slug: str) -> dict[str, Any] | None:
    return COURSE_CYCLES.get(slug)


def course_content_by_slug(cycle_slug: str, content_slug: str) -> dict[str, Any] | None:
    cycle = course_cycle_by_slug(cycle_slug)
    if not cycle:
        return None
    return next((content for content in cycle["contents"] if content["slug"] == content_slug), None)


def get_course_progress_map(user_id: int, cycle_slug: str) -> dict[str, sqlite3.Row]:
    rows = query_all("SELECT * FROM course_progress WHERE user_id = ? AND course_slug = 'escola-de-profetas' AND cycle_slug = ?", (user_id, cycle_slug))
    return {row["content_slug"]: row for row in rows}


def get_course_cycle_progress(user_id: int, cycle_slug: str) -> dict[str, int]:
    cycle = course_cycle_by_slug(cycle_slug)
    if not cycle:
        return {"done": 0, "total": 0, "percent": 0}
    progress = get_course_progress_map(user_id, cycle_slug)
    total = len(cycle["contents"])
    done = sum(1 for content in cycle["contents"] if progress.get(content["slug"]) and progress[content["slug"]]["status"] == "concluido")
    return {"done": done, "total": total, "percent": int((done / total) * 100) if total else 0}


def course_content_status(user_id: int, cycle_slug: str, content_slug: str) -> str:
    row = query_one("SELECT status FROM course_progress WHERE user_id = ? AND course_slug = 'escola-de-profetas' AND cycle_slug = ? AND content_slug = ?", (user_id, cycle_slug, content_slug))
    return row["status"] if row else "nao_iniciado"


def upsert_course_status(user_id: int, cycle_slug: str, content_slug: str, status: str) -> None:
    completed_at = now_str() if status == "concluido" else None
    execute(
        """
        INSERT INTO course_progress (user_id, course_slug, cycle_slug, content_slug, status, completed_at, updated_at)
        VALUES (?, 'escola-de-profetas', ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, cycle_slug, content_slug) DO UPDATE SET
            status = excluded.status,
            completed_at = COALESCE(excluded.completed_at, course_progress.completed_at),
            updated_at = excluded.updated_at
        """,
        (user_id, cycle_slug, content_slug, status, completed_at, now_str()),
    )


def next_course_content(cycle_slug: str, content_slug: str) -> dict[str, Any] | None:
    cycle = course_cycle_by_slug(cycle_slug)
    if not cycle:
        return None
    for index, content in enumerate(cycle["contents"]):
        if content["slug"] == content_slug and index + 1 < len(cycle["contents"]):
            return cycle["contents"][index + 1]
    return None


def seed_station_journey() -> None:
    for order, station in enumerate(station_seed_data(), start=1):
        station_id = execute(
            """
            INSERT INTO spiritual_stations
            (slug, title, subtitle, description, station_order, theme_color, icon_name, spiritual_phrase, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                station["slug"],
                station["title"],
                station["subtitle"],
                station["description"],
                order,
                "#D7A84F" if order == 1 else "#AFCFE5",
                station["icon"],
                station["phrase"],
                now_str(),
            ),
        ).lastrowid
        for lesson_order, (title, subtitle, exercise) in enumerate(station["lessons"], start=1):
            execute(
                """
                INSERT INTO station_lessons
                (station_id, lesson_order, title, subtitle, audio_url, audio_duration, lesson_text,
                 exercise_title, exercise_text, exercise_prompt, required_reflection_min_chars, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    station_id,
                    lesson_order,
                    title,
                    subtitle,
                    "",
                    "Áudio demonstrativo",
                    f"{subtitle} Esta aula convida você a caminhar com Deus de forma bíblica, simples e profunda, sem pressa e sem promessas absolutas.",
                    "Exercício de reflexão",
                    exercise,
                    "Escreva o que percebeu, o que entregou a Deus e qual pequeno passo de obediência fará hoje.",
                    80,
                    now_str(),
                ),
            )


def initialize_station_progress_for_user(user_id: int) -> None:
    stations = query_all("SELECT * FROM spiritual_stations ORDER BY station_order")
    for station in stations:
        status = "liberada" if station["station_order"] == 1 else "bloqueada"
        started = now_str() if station["station_order"] == 1 else None
        execute(
            """
            INSERT OR IGNORE INTO user_station_progress
            (user_id, station_id, status, percent_complete, started_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (user_id, station["id"], status, started, now_str()),
        )
        lessons = query_all("SELECT * FROM station_lessons WHERE station_id = ? ORDER BY lesson_order", (station["id"],))
        for lesson in lessons:
            lesson_status = "liberada" if station["station_order"] == 1 and lesson["lesson_order"] == 1 else "bloqueada"
            execute(
                """
                INSERT OR IGNORE INTO user_lesson_progress
                (user_id, lesson_id, status, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, lesson["id"], lesson_status, now_str()),
            )


def initialize_station_progress_for_all_users() -> None:
    for user in query_all("SELECT id FROM users"):
        initialize_station_progress_for_user(user["id"])


def current_user() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,)) if user_id else None


def public_test_user() -> sqlite3.Row | None:
    user = query_one("SELECT * FROM users WHERE email = ? AND role != 'admin'", ("premium@mentoria.local",))
    if user is None:
        user = query_one("SELECT * FROM users WHERE role != 'admin' ORDER BY id LIMIT 1")
    if user is None:
        return None
    course = get_course_by_slug("escola-de-profetas")
    if course:
        activate_enrollment(user["id"], course["id"])
        assign_user_product(user["id"], "escola-de-profetas", "ativo", "Acesso público temporário para testes.")
    return query_one("SELECT * FROM users WHERE id = ?", (user["id"],))


def public_test_admin() -> sqlite3.Row | None:
    admin_user = query_one("SELECT * FROM users WHERE email = ?", ("admin@escoladeprofetas.local",))
    if admin_user is None:
        admin_user = query_one("SELECT * FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    return admin_user


def require_login(next_url: str | None = None):
    user = current_user()
    if user is None and app.config["PUBLIC_TEST_ACCESS"] and not request.path.startswith("/admin"):
        user = public_test_user()
        if user is not None:
            session["user_id"] = user["id"]
            return None
    if user is None:
        return redirect(url_for("login", next=next_url or request.path))
    return None


def login_user_session(user: sqlite3.Row) -> None:
    session["user_id"] = user["id"]
    execute("UPDATE users SET last_seen_at = ?, current_page = ?, updated_at = ? WHERE id = ?", (now_str(), request.path, now_str(), user["id"]))


def logout_user_session() -> None:
    session.pop("user_id", None)


def log_activity(action: str, page: str | None = None) -> None:
    user = current_user()
    if user is None:
        return
    execute(
        "INSERT INTO activity_log (user_id, action, page, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], action, page or request.path, now_str()),
    )


def get_current_week(user: sqlite3.Row) -> int:
    if user["plan"] != "premium":
        return 1
    started = parse_dt(user["subscription_started_at"]) if user["subscription_started_at"] else now()
    return max(1, ((now() - started).days // 7) + 1)


def is_content_unlocked(user: sqlite3.Row, content: sqlite3.Row) -> bool:
    if not content["is_premium"]:
        return True
    return user["plan"] == "premium" and content["week_number"] <= get_current_week(user)


def days_until_unlock(user: sqlite3.Row, content: sqlite3.Row) -> int:
    if is_content_unlocked(user, content) or user["plan"] != "premium":
        return 0
    started = parse_dt(user["subscription_started_at"]) if user["subscription_started_at"] else now()
    unlock_date = started + timedelta(days=(content["week_number"] - 1) * 7)
    return max(1, math.ceil((unlock_date - now()).total_seconds() / 86400))


def get_unlocked_content(user: sqlite3.Row) -> list[sqlite3.Row]:
    items = query_all("SELECT * FROM content_items ORDER BY week_number, id")
    return [item for item in items if is_content_unlocked(user, item)]


def journey_items_for(user: sqlite3.Row) -> list[dict[str, Any]]:
    items = query_all("SELECT * FROM content_items ORDER BY week_number, id")
    progress = {
        row["content_id"]: row
        for row in query_all("SELECT * FROM user_progress WHERE user_id = ?", (user["id"],))
    }
    result = []
    for item in items:
        unlocked = is_content_unlocked(user, item)
        saved = progress.get(item["id"])
        status = saved["status"] if saved else ("liberado" if unlocked else "bloqueado")
        result.append(
            {
                "content": item,
                "unlocked": unlocked,
                "status": status,
                "days": days_until_unlock(user, item),
            }
        )
    return result


def week_progress(user: sqlite3.Row) -> dict[str, int]:
    current_week = get_current_week(user)
    items = [row for row in journey_items_for(user) if row["content"]["week_number"] == current_week and row["unlocked"]]
    total = len(items)
    done = sum(1 for row in items if row["status"] == "concluido")
    percent = int((done / total) * 100) if total else 0
    return {"done": done, "total": total, "percent": percent}


def require_admin() -> sqlite3.Row:
    user = current_user()
    if user is None:
        flash("Faça login para acessar o painel.", "warning")
        return None
    if user["role"] != "admin":
        flash("Acesso restrito ao painel privado da Escola.", "warning")
        return None
    return user


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if app.config["PUBLIC_TEST_ACCESS"] and (user is None or user["role"] != "admin"):
            admin_user = public_test_admin()
            if admin_user is not None:
                session["user_id"] = admin_user["id"]
                user = admin_user
        if user is None:
            return redirect(url_for("login", next=request.path))
        if user["role"] != "admin":
            flash("Acesso restrito.", "warning")
            return redirect(url_for("aluno"))
        return view(*args, **kwargs)

    return wrapped


def money_from_cents(value: int | None) -> str:
    amount = (value or 0) / 100
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def update_presence(user_id: int, current_page: str) -> None:
    timestamp = now_str()
    execute(
        "UPDATE users SET last_seen_at = ?, current_page = ?, updated_at = COALESCE(updated_at, ?) WHERE id = ?",
        (timestamp, current_page, timestamp, user_id),
    )
    execute(
        """
        INSERT INTO user_presence (user_id, last_seen_at, current_page, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            current_page = excluded.current_page,
            updated_at = excluded.updated_at
        """,
        (user_id, timestamp, current_page, timestamp, timestamp),
    )


def online_cutoff() -> str:
    return (now() - timedelta(minutes=5)).strftime(DATE_FORMAT)


def count_online_users() -> int:
    row = query_one(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE COALESCE(last_seen_at, '') >= ?
        """,
        (online_cutoff(),),
    )
    return row["total"] if row else 0


def get_online_users() -> list[sqlite3.Row]:
    return query_all(
        """
        SELECT u.*,
               GROUP_CONCAT(c.title, ', ') AS active_courses
        FROM users u
        LEFT JOIN enrollments e ON e.user_id = u.id AND e.status = 'active'
        LEFT JOIN courses c ON c.id = e.course_id
        WHERE COALESCE(u.last_seen_at, '') >= ?
        GROUP BY u.id
        ORDER BY u.last_seen_at DESC
        """,
        (online_cutoff(),),
    )


def calculate_cycle_progress(user_id: int, course_slug: str, cycle_slug: str) -> dict[str, int]:
    if course_slug != "escola-de-profetas":
        return {"done": 0, "total": 0, "percent": 0}
    return get_course_cycle_progress(user_id, cycle_slug)


def calculate_user_course_progress(user_id: int, course_slug: str) -> dict[str, int]:
    if course_slug != "escola-de-profetas":
        return {"done": 0, "total": 0, "percent": 0}
    total = sum(len(cycle["contents"]) for cycle in COURSE_CYCLES.values())
    done_row = query_one(
        """
        SELECT COUNT(*) AS total
        FROM course_progress
        WHERE user_id = ?
          AND course_slug = ?
          AND status = 'concluido'
        """,
        (user_id, course_slug),
    )
    done = done_row["total"] if done_row else 0
    return {"done": done, "total": total, "percent": int((done / total) * 100) if total else 0}


def current_cycle_for_user(user_id: int) -> str:
    for cycle in COURSE_CYCLES.values():
        progress = calculate_cycle_progress(user_id, "escola-de-profetas", cycle["slug"])
        if progress["percent"] < 100:
            return cycle["name"]
    return "Concluído"


def csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def log_station_activity(user_id: int, action: str, station_id: int | None = None, lesson_id: int | None = None, details: str | None = None) -> None:
    execute(
        "INSERT INTO station_activity_log (user_id, action, station_id, lesson_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, station_id, lesson_id, details, now_str()),
    )


def get_station_progress(user_id: int, station_id: int) -> dict[str, Any]:
    lessons = query_all("SELECT id FROM station_lessons WHERE station_id = ? ORDER BY lesson_order", (station_id,))
    total = len(lessons)
    if not total:
        return {"done": 0, "total": 0, "percent": 0}
    ids = tuple(row["id"] for row in lessons)
    placeholders = ",".join("?" for _ in ids)
    done = query_one(
        f"SELECT COUNT(*) AS total FROM user_lesson_progress WHERE user_id = ? AND lesson_id IN ({placeholders}) AND status = 'concluida'",
        (user_id, *ids),
    )["total"]
    percent = int((done / total) * 100)
    return {"done": done, "total": total, "percent": percent}


def get_journey_progress(user_id: int) -> dict[str, Any]:
    total = query_one("SELECT COUNT(*) AS total FROM station_lessons")["total"]
    done = query_one("SELECT COUNT(*) AS total FROM user_lesson_progress WHERE user_id = ? AND status = 'concluida'", (user_id,))["total"]
    percent = int((done / total) * 100) if total else 0
    stations_done = query_one("SELECT COUNT(*) AS total FROM user_station_progress WHERE user_id = ? AND status = 'concluida'", (user_id,))["total"]
    return {"done": done, "total": total, "percent": percent, "stations_done": stations_done, "stations_total": 7}


def get_user_current_station(user_id: int) -> sqlite3.Row | None:
    station = query_one(
        """
        SELECT s.*, p.status, p.percent_complete
        FROM spiritual_stations s
        JOIN user_station_progress p ON p.station_id = s.id
        WHERE p.user_id = ? AND p.status IN ('liberada', 'em_andamento')
        ORDER BY s.station_order
        LIMIT 1
        """,
        (user_id,),
    )
    if station:
        return station
    return query_one(
        """
        SELECT s.*, p.status, p.percent_complete
        FROM spiritual_stations s
        JOIN user_station_progress p ON p.station_id = s.id
        WHERE p.user_id = ?
        ORDER BY s.station_order DESC
        LIMIT 1
        """,
        (user_id,),
    )


def unlock_next_lesson(user_id: int, lesson_id: int) -> sqlite3.Row | None:
    lesson = query_one("SELECT * FROM station_lessons WHERE id = ?", (lesson_id,))
    if not lesson:
        return None
    next_lesson = query_one(
        "SELECT * FROM station_lessons WHERE station_id = ? AND lesson_order = ?",
        (lesson["station_id"], lesson["lesson_order"] + 1),
    )
    if next_lesson:
        execute(
            "UPDATE user_lesson_progress SET status = 'liberada', updated_at = ? WHERE user_id = ? AND lesson_id = ? AND status = 'bloqueada'",
            (now_str(), user_id, next_lesson["id"]),
        )
        log_station_activity(user_id, "liberou aula", lesson["station_id"], next_lesson["id"], "Nova etapa liberada")
    return next_lesson


def unlock_next_station(user_id: int, station_id: int) -> sqlite3.Row | None:
    station = query_one("SELECT * FROM spiritual_stations WHERE id = ?", (station_id,))
    if not station:
        return None
    next_station = query_one("SELECT * FROM spiritual_stations WHERE station_order = ?", (station["station_order"] + 1,))
    if next_station:
        first_lesson = query_one("SELECT * FROM station_lessons WHERE station_id = ? ORDER BY lesson_order LIMIT 1", (next_station["id"],))
        execute(
            "UPDATE user_station_progress SET status = 'liberada', started_at = ?, updated_at = ? WHERE user_id = ? AND station_id = ? AND status = 'bloqueada'",
            (now_str(), now_str(), user_id, next_station["id"]),
        )
        if first_lesson:
            execute(
                "UPDATE user_lesson_progress SET status = 'liberada', updated_at = ? WHERE user_id = ? AND lesson_id = ?",
                (now_str(), user_id, first_lesson["id"]),
            )
        log_station_activity(user_id, "liberou estacao", next_station["id"], first_lesson["id"] if first_lesson else None, "Nova estação liberada")
    return next_station


def refresh_station_completion(user_id: int, station_id: int) -> None:
    progress = get_station_progress(user_id, station_id)
    status = "concluida" if progress["percent"] == 100 else ("em_andamento" if progress["done"] else "liberada")
    completed_at = now_str() if status == "concluida" else None
    execute(
        """
        UPDATE user_station_progress
        SET status = ?, percent_complete = ?, completed_at = COALESCE(?, completed_at), updated_at = ?
        WHERE user_id = ? AND station_id = ?
        """,
        (status, progress["percent"], completed_at, now_str(), user_id, station_id),
    )
    if status == "concluida":
        unlock_next_station(user_id, station_id)


def mark_audio_listened(user_id: int, lesson_id: int) -> tuple[bool, str]:
    progress = query_one("SELECT * FROM user_lesson_progress WHERE user_id = ? AND lesson_id = ?", (user_id, lesson_id))
    if not progress or progress["status"] == "bloqueada":
        return False, "Esta aula ainda está bloqueada."
    new_status = "audio_ouvido" if progress["status"] == "liberada" else progress["status"]
    execute(
        "UPDATE user_lesson_progress SET status = ?, listened_at = COALESCE(listened_at, ?), updated_at = ? WHERE user_id = ? AND lesson_id = ?",
        (new_status, now_str(), now_str(), user_id, lesson_id),
    )
    lesson = query_one("SELECT station_id FROM station_lessons WHERE id = ?", (lesson_id,))
    log_station_activity(user_id, "ouviu audio", lesson["station_id"] if lesson else None, lesson_id)
    return True, "Áudio marcado como ouvido."


def complete_lesson_exercise(user_id: int, lesson_id: int, answer: str) -> tuple[bool, str, dict[str, Any]]:
    lesson = query_one("SELECT * FROM station_lessons WHERE id = ?", (lesson_id,))
    progress = query_one("SELECT * FROM user_lesson_progress WHERE user_id = ? AND lesson_id = ?", (user_id, lesson_id))
    if not lesson or not progress or progress["status"] == "bloqueada":
        return False, "Esta aula ainda está bloqueada.", {}
    if not progress["listened_at"] and progress["status"] != "audio_ouvido":
        return False, "Marque o áudio como ouvido antes de concluir o exercício.", {}
    if len(answer.strip()) < lesson["required_reflection_min_chars"]:
        return False, f"Escreva um pouco mais. Mínimo: {lesson['required_reflection_min_chars']} caracteres.", {}
    execute(
        """
        UPDATE user_lesson_progress
        SET status = 'concluida', exercise_answer = ?, completed_at = ?, updated_at = ?
        WHERE user_id = ? AND lesson_id = ?
        """,
        (answer.strip(), now_str(), now_str(), user_id, lesson_id),
    )
    log_station_activity(user_id, "concluiu aula", lesson["station_id"], lesson_id)
    next_lesson = unlock_next_lesson(user_id, lesson_id)
    refresh_station_completion(user_id, lesson["station_id"])
    return True, "Etapa concluída. A próxima aula foi liberada para você.", {"next_lesson_id": next_lesson["id"] if next_lesson else None}


def station_view_models(user_id: int) -> list[dict[str, Any]]:
    stations = query_all("SELECT * FROM spiritual_stations ORDER BY station_order")
    current = get_user_current_station(user_id)
    result = []
    for station in stations:
        saved = query_one("SELECT * FROM user_station_progress WHERE user_id = ? AND station_id = ?", (user_id, station["id"]))
        progress = get_station_progress(user_id, station["id"])
        result.append({"station": station, "saved": saved, "progress": progress, "is_current": current and current["id"] == station["id"]})
    return result


def cycle_by_slug(slug: str) -> dict[str, Any] | None:
    return next((cycle for cycle in FORMATION_CYCLES if cycle["slug"] == slug), None)


def cycle_module_rows(user_id: int, cycle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for slug in cycle["modules"]:
        station = query_one("SELECT * FROM spiritual_stations WHERE slug = ?", (slug,))
        if not station:
            continue
        saved = query_one("SELECT * FROM user_station_progress WHERE user_id = ? AND station_id = ?", (user_id, station["id"]))
        rows.append({"station": station, "saved": saved, "progress": get_station_progress(user_id, station["id"])})
    return rows


def cycle_progress(user_id: int, cycle: dict[str, Any]) -> dict[str, Any]:
    modules = cycle_module_rows(user_id, cycle)
    total = len(modules)
    done = sum(1 for row in modules if row["saved"] and row["saved"]["status"] == "concluida")
    percent = int((done / total) * 100) if total else 0
    return {"done": done, "total": total, "percent": percent}


def is_cycle_unlocked(user_id: int, cycle_index: int) -> bool:
    if cycle_index == 0:
        return True
    previous = FORMATION_CYCLES[cycle_index - 1]
    return cycle_progress(user_id, previous)["percent"] == 100


def sync_cycle_unlocks_for_user(user_id: int) -> None:
    for index, cycle in enumerate(FORMATION_CYCLES):
        if not is_cycle_unlocked(user_id, index):
            continue
        for row in cycle_module_rows(user_id, cycle):
            station = row["station"]
            saved = row["saved"]
            if saved and saved["status"] == "bloqueada":
                execute(
                    "UPDATE user_station_progress SET status = 'liberada', started_at = COALESCE(started_at, ?), updated_at = ? WHERE user_id = ? AND station_id = ?",
                    (now_str(), now_str(), user_id, station["id"]),
                )
                first_lesson = query_one("SELECT * FROM station_lessons WHERE station_id = ? ORDER BY lesson_order LIMIT 1", (station["id"],))
                if first_lesson:
                    execute(
                        "UPDATE user_lesson_progress SET status = 'liberada', updated_at = ? WHERE user_id = ? AND lesson_id = ? AND status = 'bloqueada'",
                        (now_str(), user_id, first_lesson["id"]),
                    )


def cycle_view_models(user_id: int) -> list[dict[str, Any]]:
    sync_cycle_unlocks_for_user(user_id)
    models = []
    for index, cycle in enumerate(FORMATION_CYCLES):
        progress = cycle_progress(user_id, cycle)
        unlocked = is_cycle_unlocked(user_id, index)
        status = "bloqueado"
        if unlocked:
            status = "concluído" if progress["percent"] == 100 else ("em andamento" if progress["done"] else "liberado")
        models.append({"cycle": cycle, "progress": progress, "status": status, "unlocked": unlocked, "modules": cycle_module_rows(user_id, cycle)})
    return models


@app.before_request
def auto_login_admin_for_testing() -> None:
    if not app.config["AUTO_LOGIN_ADMIN"]:
        return
    if request.endpoint in {"static"}:
        return
    if session.get("user_id"):
        return
    admin_user = public_test_admin()
    if admin_user is not None:
        session["user_id"] = admin_user["id"]


@app.before_request
def auto_login_public_test_access() -> None:
    if not app.config["PUBLIC_TEST_ACCESS"]:
        return
    if request.endpoint in {"static"} or request.path.startswith("/admin"):
        return
    current = current_user()
    if current is not None and current["role"] == "admin":
        return
    user = public_test_user()
    if user is not None:
        session["user_id"] = user["id"]


@app.before_request
def track_page() -> None:
    if request.endpoint in {"static", "api_ping"}:
        return
    user = current_user()
    if user is None:
        return
    update_presence(user["id"], request.path)


@app.context_processor
def inject_context() -> dict[str, Any]:
    user = current_user()
    users = query_all("SELECT id, name, plan, role FROM users ORDER BY id")
    school_current_station = None
    school_journey = {"done": 0, "total": 0, "percent": 0, "stations_done": 0, "stations_total": 7}
    school_next_lesson = None
    try:
        if user is not None:
            initialize_station_progress_for_user(user["id"])
            school_current_station = get_user_current_station(user["id"])
            school_journey = get_journey_progress(user["id"])
            school_next_lesson = query_one(
                """
                SELECT l.*, s.title AS station_title, p.status
                FROM station_lessons l
                JOIN spiritual_stations s ON s.id = l.station_id
                JOIN user_lesson_progress p ON p.lesson_id = l.id AND p.user_id = ?
                WHERE p.status IN ('liberada', 'audio_ouvido')
                ORDER BY s.station_order, l.lesson_order
                LIMIT 1
                """,
                (user["id"],),
            )
    except sqlite3.Error:
        pass
    return {
        "user": user,
        "demo_users": users,
        "public_test_access": app.config["PUBLIC_TEST_ACCESS"],
        "current_week": get_current_week(user) if user is not None else 1,
        "school_current_station": school_current_station,
        "school_journey": school_journey,
        "school_next_lesson": school_next_lesson,
    }


@app.route("/")
def index():
    log_activity("abriu pagina")
    return render_template("index.html")


@app.route("/cursos")
def cursos():
    log_activity("abriu cursos")
    products = query_all("SELECT * FROM products WHERE is_active = 1 ORDER BY id")
    user = current_user()
    user_products = {}
    if user is not None:
        user_products = {
            row["slug"]: row
            for row in query_all(
                """
                SELECT p.slug, up.status, up.acquired_at
                FROM user_products up
                JOIN products p ON p.id = up.product_id
                WHERE up.user_id = ?
                """,
                (user["id"],),
            )
        }
    return render_template("cursos.html", products=products, user_products=user_products)


@app.post("/cursos/<slug>/interesse")
def product_interest(slug: str):
    return redirect(url_for("comprar_curso", slug=slug))


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next") or request.form.get("next") or url_for("aluno")
    if request.method == "GET" and app.config["PUBLIC_TEST_ACCESS"]:
        test_user = public_test_admin() if next_url.startswith("/admin") else public_test_user()
        if test_user is not None:
            session["user_id"] = test_user["id"]
            return redirect(next_url)
    if current_user() is not None and request.method == "GET":
        return redirect(next_url)
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            login_user_session(user)
            flash("Login realizado com sucesso.", "success")
            return redirect(next_url)
        flash("E-mail ou senha inválidos.", "warning")
    return render_template("login.html", next_url=next_url)


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    next_url = request.args.get("next") or request.form.get("next") or url_for("aluno")
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not name or not email or not password:
            flash("Preencha nome, e-mail e senha.", "warning")
            return render_template("cadastro.html", next_url=next_url)
        if password != confirm:
            flash("As senhas não conferem.", "warning")
            return render_template("cadastro.html", next_url=next_url)
        existing = query_one("SELECT id FROM users WHERE email = ?", (email,))
        if existing:
            flash("Já existe uma conta com este e-mail. Faça login para continuar.", "warning")
            return redirect(url_for("login", next=next_url))
        execute(
            """
            INSERT INTO users
            (name, email, password_hash, plan, role, spiritual_profile, subscription_started_at, created_at, last_seen_at, current_page, updated_at)
            VALUES (?, ?, ?, 'free', 'user', NULL, NULL, ?, ?, ?, ?)
            """,
            (name, email, generate_password_hash(password), now_str(), now_str(), next_url, now_str()),
        )
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        initialize_station_progress_for_user(user["id"])
        login_user_session(user)
        flash("Cadastro criado. Continue sua inscrição.", "success")
        return redirect(next_url)
    return render_template("cadastro.html", next_url=next_url)


@app.route("/adquirir/escola-de-profetas")
def adquirir_escola_de_profetas():
    user = current_user()
    next_url = url_for("adquirir_escola_de_profetas")
    if user is None:
        return redirect(url_for("cadastro", next=next_url))
    course = get_course_by_slug("escola-de-profetas")
    if not course:
        flash("Curso não encontrado.", "warning")
        return redirect(url_for("cursos"))
    if user_has_active_enrollment(user["id"], "escola-de-profetas"):
        return redirect(url_for("aluno"))
    get_or_create_pending_purchase(user["id"], course["id"])
    return redirect(url_for("checkout_escola_de_profetas"))


@app.route("/checkout/escola-de-profetas")
def checkout_escola_de_profetas():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    course = get_course_by_slug("escola-de-profetas")
    if user_has_active_enrollment(user["id"], "escola-de-profetas"):
        return redirect(url_for("aluno"))
    purchase = get_or_create_pending_purchase(user["id"], course["id"])
    return render_template("checkout.html", course=course, purchase=purchase)


@app.post("/checkout/escola-de-profetas/simular-pagamento")
def simular_pagamento_escola_de_profetas():
    login_redirect = require_login(url_for("checkout_escola_de_profetas"))
    if login_redirect:
        return login_redirect
    user = current_user()
    course = get_course_by_slug("escola-de-profetas")
    purchase = get_or_create_pending_purchase(user["id"], course["id"])
    mark_purchase_paid_by_id(purchase["id"], purchase["payment_reference"])
    assign_user_product(user["id"], "escola-de-profetas", "ativo", "Pagamento aprovado no checkout novo.")
    flash("Pagamento confirmado. Seu acesso foi liberado.", "success")
    return redirect(url_for("aluno"))


@app.post("/webhook/payment")
def webhook_payment():
    # Produção: validar a assinatura oficial do gateway antes de usar este endpoint.
    if request.headers.get("X-Webhook-Token") != app.config["WEBHOOK_TOKEN"]:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    course_slug = (payload.get("course_slug") or "escola-de-profetas").strip()
    status = (payload.get("status") or "").strip()
    reference = (payload.get("payment_reference") or "").strip() or None
    user = query_one("SELECT * FROM users WHERE email = ?", (email,))
    course = get_course_by_slug(course_slug)
    if not user or not course:
        return jsonify({"ok": False, "error": "user_or_course_not_found"}), 404
    purchase = get_or_create_pending_purchase(user["id"], course["id"])
    if status == "paid":
        mark_purchase_paid_by_id(purchase["id"], reference)
    else:
        execute(
            "UPDATE purchases SET status = ?, payment_reference = COALESCE(?, payment_reference), updated_at = ? WHERE id = ?",
            (status or "pending", reference, now_str(), purchase["id"]),
        )
    return jsonify({"ok": True})


@app.route("/comprar/<slug>", methods=["GET", "POST"])
def comprar_curso(slug: str):
    if slug == "escola-de-profetas":
        return redirect(url_for("adquirir_escola_de_profetas"))
    product = query_one("SELECT * FROM products WHERE slug = ? AND is_active = 1", (slug,))
    if not product:
        flash("Curso não encontrado.", "warning")
        return redirect(url_for("cursos"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not name or not email or not password:
            flash("Preencha seus dados para seguir para o pagamento.", "warning")
            return render_template("comprar.html", product=product)
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if not user:
            execute(
                """
                INSERT INTO users
                (name, email, password_hash, plan, role, spiritual_profile, subscription_started_at, created_at, last_seen_at, current_page, updated_at)
                VALUES (?, ?, ?, 'free', 'user', NULL, NULL, ?, ?, ?, ?)
                """,
                (name, email, generate_password_hash(password), now_str(), now_str(), f"/comprar/{slug}", now_str()),
            )
            user = query_one("SELECT * FROM users WHERE email = ?", (email,))
            initialize_station_progress_for_user(user["id"])
        login_user_session(user)
        assign_user_product(user["id"], slug, "aguardando_pagamento", "Pedido iniciado na página de cursos.")
        cur = execute(
            """
            INSERT INTO purchase_orders
            (user_id, product_id, status, amount_label, checkout_reference, created_at, updated_at)
            VALUES (?, ?, 'aguardando_pagamento', ?, ?, ?, ?)
            """,
            (user["id"], product["id"], product["price_label"] or "A definir", f"checkout-{slug}-{int(now().timestamp())}", now_str(), now_str()),
        )
        log_activity("iniciou compra", f"/comprar/{slug}")
        return redirect(url_for("pagamento", order_id=cur.lastrowid))
    log_activity("abriu compra", f"/comprar/{slug}")
    return render_template("comprar.html", product=product)


@app.route("/pagamento/<int:order_id>", methods=["GET", "POST"])
def pagamento(order_id: int):
    order = query_one(
        """
        SELECT o.*, p.slug, p.name AS product_name, p.subtitle, p.description, u.email, u.name AS user_name
        FROM purchase_orders o
        JOIN products p ON p.id = o.product_id
        JOIN users u ON u.id = o.user_id
        WHERE o.id = ?
        """,
        (order_id,),
    )
    if not order:
        flash("Pedido não encontrado.", "warning")
        return redirect(url_for("cursos"))
    session["user_id"] = order["user_id"]
    if request.method == "POST":
        execute("UPDATE purchase_orders SET status = 'pago', paid_at = ?, updated_at = ? WHERE id = ?", (now_str(), now_str(), order_id))
        assign_user_product(order["user_id"], order["slug"], "ativo", "Pagamento aprovado no protótipo.")
        if order["slug"] == "escola-de-profetas":
            execute(
                "UPDATE users SET plan = 'premium', subscription_started_at = COALESCE(subscription_started_at, ?) WHERE id = ?",
                (now_str(), order["user_id"]),
            )
        log_activity("pagamento aprovado", f"/pagamento/{order_id}")
        flash("Pagamento aprovado. Seus dados de acesso foram ativados automaticamente.", "success")
        return redirect(url_for("minha_jornada"))
    log_activity("abriu pagamento", f"/pagamento/{order_id}")
    return render_template("pagamento.html", order=order)


@app.route("/logout")
def logout():
    logout_user_session()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("cursos"))


@app.route("/trocar-usuario/<int:user_id>")
def switch_user(user_id: int):
    user = query_one("SELECT id FROM users WHERE id = ?", (user_id,))
    if user:
        session["user_id"] = user["id"]
        flash("Usuário demo alterado.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/free")
def free():
    return redirect(url_for("cursos"))


@app.route("/crescer")
@app.route("/upgrade")
def upgrade():
    return redirect(url_for("cursos"))


@app.route("/premium")
def premium():
    return redirect(url_for("estacoes"))


@app.post("/simular-assinatura")
def simulate_subscription():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    months = request.form.get("months")
    started = now() - timedelta(days=183) if months == "6" else now()
    user = current_user()
    execute(
        "UPDATE users SET plan = 'premium', subscription_started_at = ? WHERE id = ?",
        (started.strftime(DATE_FORMAT), user["id"]),
    )
    log_activity("simulou assinatura premium")
    flash("Assinatura premium simulada com sucesso.", "success")
    return redirect(url_for("minha_jornada"))


@app.route("/diagnostico", methods=["GET", "POST"])
def diagnostico():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    options = [
        ("reconexao", "Estou recomeçando minha vida com Deus."),
        ("paz", "Estou ansiosa e sem direção."),
        ("discernimento", "Quero crescer em discernimento espiritual."),
        ("chamado", "Quero entender meu chamado."),
        ("oracao", "Quero fortalecer minha vida de oração."),
        ("anjos", "Quero aprender sobre proteção espiritual e anjos com base bíblica."),
        ("maturidade", "Quero maturidade ministerial."),
    ]
    if request.method == "POST":
        profile = request.form.get("spiritual_profile")
        if profile in {item[0] for item in options}:
            execute("UPDATE users SET spiritual_profile = ? WHERE id = ?", (profile, current_user()["id"]))
            log_activity("respondeu diagnostico")
            flash("Diagnóstico salvo. Sua formação foi ajustada com carinho.", "success")
            return redirect(url_for("minha_jornada"))
        flash("Escolha uma opção para salvar seu diagnóstico.", "warning")
    log_activity("abriu pagina")
    return render_template("diagnostico.html", options=options)


@app.route("/aluno")
@app.route("/minha-jornada", endpoint="minha_jornada")
def aluno():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    log_activity("abriu pagina")
    purchased_products = get_user_courses(user["id"])
    return render_template("journey.html", purchased_products=purchased_products)


@app.post("/conteudo/<int:content_id>/concluir")
def complete_content(content_id: int):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    content = query_one("SELECT * FROM content_items WHERE id = ?", (content_id,))
    if content and is_content_unlocked(user, content):
        execute(
            """
            INSERT INTO user_progress (user_id, content_id, status, completed_at, updated_at)
            VALUES (?, ?, 'concluido', ?, ?)
            ON CONFLICT(user_id, content_id)
            DO UPDATE SET status = 'concluido', completed_at = excluded.completed_at, updated_at = excluded.updated_at
            """,
            (user["id"], content_id, now_str(), now_str()),
        )
        log_activity("concluiu conteudo", f"/conteudo/{content_id}")
        flash("Conteúdo marcado como concluído.", "success")
    return redirect(url_for("minha_jornada"))


@app.route("/duvidas", methods=["GET", "POST"])
def duvidas():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    categories = ["Oração", "Discernimento", "Anjos e proteção espiritual", "Propósito", "Dons espirituais", "Ansiedade e vida emocional", "Família", "Vida com Deus", "Dúvida bíblica", "Outro"]
    month_start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(DATE_FORMAT)
    sent_this_month = query_one(
        "SELECT COUNT(*) AS total FROM questions_channel WHERE user_id = ? AND created_at >= ?",
        (user["id"], month_start),
    )["total"]
    limit = 2 if user["plan"] == "premium" else 1
    if request.method == "POST":
        if sent_this_month >= limit:
            flash("Limite mensal atingido para este protótipo.", "warning")
            return redirect(url_for("duvidas"))
        category = request.form.get("category", "Outro")
        question = request.form.get("question", "").strip()
        share = 1 if request.form.get("share_anonymous") else 0
        if category not in categories or not question:
            flash("Preencha categoria e dúvida.", "warning")
        else:
            is_sensitive = int(any(word in question.lower() for word in ["abuso", "suic", "violência", "violencia", "pânico", "panico"]))
            execute(
                "INSERT INTO questions_channel (user_id, category, question, status, is_sensitive, share_anonymous, created_at) VALUES (?, ?, ?, 'nova', ?, ?, ?)",
                (user["id"], category, question, is_sensitive, share, now_str()),
            )
            log_activity("enviou duvida")
            flash("Dúvida enviada. A Escola poderá responder em até 7 dias.", "success")
            return redirect(url_for("duvidas"))
    questions = query_all("SELECT * FROM questions_channel WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))
    log_activity("abriu pagina")
    return render_template("duvidas.html", categories=categories, questions=questions, sent_this_month=sent_this_month, limit=limit)


@app.route("/duvidas-da-semana")
def duvidas_semana():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    answered = query_all(
        "SELECT category, question, answer, answered_at FROM questions_channel WHERE status = 'respondida' AND share_anonymous = 1 AND answer IS NOT NULL ORDER BY answered_at DESC"
    )
    log_activity("abriu pagina")
    return render_template("weekly_questions.html", answered=answered)


@app.route("/oracao", methods=["GET", "POST"])
def oracao():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    return redirect(url_for("minha_jornada"))


@app.route("/diario", methods=["GET", "POST"])
def diario():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    return redirect(url_for("minha_jornada"))


@app.route("/mapa-ministerial", methods=["GET", "POST"])
def mapa_ministerial():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    gifts = ["Pastor", "Apóstolo", "Mestre", "Profeta", "Evangelista"]
    questions = {
        "Pastor": ["Cuido de pessoas com constância.", "Percebo quando alguém precisa de acolhimento.", "Gosto de acompanhar processos longos.", "Tenho sensibilidade para restaurar.", "Valorizo comunhão e cuidado."],
        "Apóstolo": ["Vejo caminhos onde ainda não há estrutura.", "Gosto de iniciar projetos com propósito.", "Penso em expansão do Reino.", "Consigo mobilizar pessoas para uma missão.", "Tenho facilidade com visão e construção."],
        "Mestre": ["Amo estudar a Palavra com profundidade.", "Gosto de explicar temas difíceis com clareza.", "Valorizo doutrina saudável.", "Percebo incoerências com atenção.", "Sinto alegria em formar entendimento."],
        "Profeta": ["Sou sensível ao arrependimento e santidade.", "Percebo quando algo precisa ser confrontado com amor.", "Valorizo ouvir Deus com temor.", "Tenho zelo pela verdade.", "Sinto peso por alinhamento espiritual."],
        "Evangelista": ["Tenho facilidade para falar de Jesus.", "Sinto compaixão por quem está longe da fé.", "Gosto de convidar pessoas para recomeçar.", "Comunico esperança de forma simples.", "Valorizo testemunhos de salvação."],
    }
    result = None
    if request.method == "POST":
        scores = {}
        for gift, items in questions.items():
            total = 0
            for idx, _ in enumerate(items):
                total += int(request.form.get(f"{gift}_{idx}", "1"))
            scores[gift] = {"score": total, "percent": int((total / 25) * 100)}
        ordered = sorted(scores.items(), key=lambda pair: pair[1]["score"], reverse=True)
        result = {"scores": scores, "top": [item[0] for item in ordered[:3]]}
        log_activity("respondeu mapa ministerial")
    else:
        log_activity("abriu pagina")
    return render_template("ministerial_map.html", gifts=gifts, questions=questions, result=result)


@app.route("/estacoes")
@app.route("/ciclos")
def estacoes():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Este curso ainda não está liberado para o seu acesso.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    initialize_station_progress_for_user(user["id"])
    sync_cycle_unlocks_for_user(user["id"])
    log_activity("abriu estacoes")
    return render_template(
        "estacoes.html",
        cycles=cycle_view_models(user["id"]),
        journey=get_journey_progress(user["id"]),
    )


@app.route("/curso/escola-de-profetas")
def curso_escola_de_profetas():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Adquira o curso para acessar a formação.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    return redirect(url_for("estacoes"))


@app.route("/media/<kind>/<path:filename>")
def protected_media(kind: str, filename: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if kind not in {"videos", "pdfs"} or not has_confirmed_product(user["id"], "escola-de-profetas"):
        abort(403)
    return send_from_directory(PROTECTED_MEDIA_DIR / kind, filename)


@app.route("/ciclo/<slug>")
def cycle_detail(slug: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Este curso ainda não está liberado para o seu acesso.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    initialize_station_progress_for_user(user["id"])
    sync_cycle_unlocks_for_user(user["id"])
    cycle = course_cycle_by_slug(slug)
    if not cycle:
        flash("Ciclo não encontrado.", "warning")
        return redirect(url_for("estacoes"))
    legacy_cycle = cycle_by_slug(slug)
    cycle_index = next(index for index, item in enumerate(FORMATION_CYCLES) if item["slug"] == slug)
    cycle_unlocked = True
    progress_map = get_course_progress_map(user["id"], slug)
    contents = []
    for content in cycle["contents"]:
        saved = progress_map.get(content["slug"])
        video_exists = (PROTECTED_MEDIA_DIR / content["video_path"]).exists()
        pdf_exists = (PROTECTED_MEDIA_DIR / content["pdf_path"]).exists()
        contents.append(
            {
                "content": content,
                "status": saved["status"] if saved else "nao_iniciado",
                "video_exists": video_exists,
                "pdf_exists": pdf_exists,
            }
        )
    log_activity("abriu ciclo")
    return render_template(
        "cycle_detail.html",
        cycle=cycle,
        legacy_cycle=legacy_cycle,
        contents=contents,
        progress=get_course_cycle_progress(user["id"], slug),
        cycle_unlocked=cycle_unlocked,
    )


@app.route("/curso/<cycle_slug>/<content_slug>")
def course_content_detail(cycle_slug: str, content_slug: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Este curso ainda não está liberado para o seu acesso.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    cycle = course_cycle_by_slug(cycle_slug)
    content = course_content_by_slug(cycle_slug, content_slug)
    if not cycle or not content:
        flash("Conteúdo não encontrado.", "warning")
        return redirect(url_for("estacoes"))
    status = course_content_status(user["id"], cycle_slug, content_slug)
    if status == "nao_iniciado":
        upsert_course_status(user["id"], cycle_slug, content_slug, "em_andamento")
        status = "em_andamento"
    comment = query_one(
        "SELECT * FROM course_comments WHERE user_id = ? AND course_slug = 'escola-de-profetas' AND cycle_slug = ? AND content_slug = ?",
        (user["id"], cycle_slug, content_slug),
    )
    log_activity("abriu conteudo do curso")
    return render_template(
        "course_content.html",
        cycle=cycle,
        content=content,
        status=status,
        comment=comment,
        progress=get_course_cycle_progress(user["id"], cycle_slug),
        next_content=next_course_content(cycle_slug, content_slug),
        video_exists=(PROTECTED_MEDIA_DIR / content["video_path"]).exists(),
        pdf_exists=(PROTECTED_MEDIA_DIR / content["pdf_path"]).exists(),
    )


@app.post("/curso/<cycle_slug>/<content_slug>/comentario")
def save_course_comment(cycle_slug: str, content_slug: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Este curso ainda não está liberado para o seu acesso.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    if not course_content_by_slug(cycle_slug, content_slug):
        flash("Conteúdo não encontrado.", "warning")
        return redirect(url_for("estacoes"))
    text = (request.form.get("comment_text") or "").strip()
    if not text:
        flash("Escreva sua reflexão antes de salvar.", "warning")
        return redirect(url_for("course_content_detail", cycle_slug=cycle_slug, content_slug=content_slug))
    execute(
        """
        INSERT INTO course_comments (user_id, course_slug, cycle_slug, content_slug, comment_text, created_at, updated_at)
        VALUES (?, 'escola-de-profetas', ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, cycle_slug, content_slug) DO UPDATE SET
            comment_text = excluded.comment_text,
            updated_at = excluded.updated_at
        """,
        (user["id"], cycle_slug, content_slug, text, now_str(), now_str()),
    )
    if course_content_status(user["id"], cycle_slug, content_slug) == "nao_iniciado":
        upsert_course_status(user["id"], cycle_slug, content_slug, "em_andamento")
    log_activity("salvou reflexao do curso")
    flash("Reflexão salva.", "success")
    return redirect(url_for("course_content_detail", cycle_slug=cycle_slug, content_slug=content_slug))


@app.post("/curso/<cycle_slug>/<content_slug>/concluir")
def complete_course_content(cycle_slug: str, content_slug: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Este curso ainda não está liberado para o seu acesso.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    if not course_content_by_slug(cycle_slug, content_slug):
        flash("Conteúdo não encontrado.", "warning")
        return redirect(url_for("estacoes"))
    upsert_course_status(user["id"], cycle_slug, content_slug, "concluido")
    log_activity("concluiu conteudo do curso")
    flash("Conteúdo marcado como concluído.", "success")
    next_content = next_course_content(cycle_slug, content_slug)
    if next_content:
        return redirect(url_for("course_content_detail", cycle_slug=cycle_slug, content_slug=next_content["slug"]))
    return redirect(url_for("cycle_detail", slug=cycle_slug))


@app.route("/estacao/<slug>")
def station_detail(slug: str):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Adquira o curso para acessar a formação.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    initialize_station_progress_for_user(user["id"])
    sync_cycle_unlocks_for_user(user["id"])
    station = query_one("SELECT * FROM spiritual_stations WHERE slug = ?", (slug,))
    if not station:
        flash("Estação não encontrada.", "warning")
        return redirect(url_for("estacoes"))
    saved = query_one("SELECT * FROM user_station_progress WHERE user_id = ? AND station_id = ?", (user["id"], station["id"]))
    if saved and saved["status"] == "bloqueada":
        flash("Esta estação ainda será liberada.", "warning")
        return redirect(url_for("estacoes"))
    lessons = query_all(
        """
        SELECT l.*, p.status, p.listened_at, p.completed_at
        FROM station_lessons l
        JOIN user_lesson_progress p ON p.lesson_id = l.id AND p.user_id = ?
        WHERE l.station_id = ?
        ORDER BY l.lesson_order
        """,
        (user["id"], station["id"]),
    )
    log_station_activity(user["id"], "abriu estacao", station["id"])
    return render_template("station_detail.html", station=station, saved=saved, lessons=lessons, progress=get_station_progress(user["id"], station["id"]))


@app.route("/aula/<int:lesson_id>")
def lesson_detail(lesson_id: int):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        flash("Adquira o curso para acessar a formação.", "warning")
        return redirect(url_for("adquirir_escola_de_profetas"))
    initialize_station_progress_for_user(user["id"])
    lesson = query_one(
        """
        SELECT l.*, s.title AS station_title, s.slug AS station_slug, s.spiritual_phrase
        FROM station_lessons l
        JOIN spiritual_stations s ON s.id = l.station_id
        WHERE l.id = ?
        """,
        (lesson_id,),
    )
    progress = query_one("SELECT * FROM user_lesson_progress WHERE user_id = ? AND lesson_id = ?", (user["id"], lesson_id))
    if not lesson or not progress or progress["status"] == "bloqueada":
        flash("Esta aula ainda está bloqueada.", "warning")
        return redirect(url_for("estacoes"))
    log_station_activity(user["id"], "abriu aula", lesson["station_id"], lesson_id)
    return render_template("lesson.html", lesson=lesson, progress=progress)


@app.post("/api/lesson/<int:lesson_id>/listened")
def api_lesson_listened(lesson_id: int):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        return jsonify({"ok": False, "message": "Curso não liberado."}), 403
    ok, message = mark_audio_listened(user["id"], lesson_id)
    return jsonify({"ok": ok, "message": message})


@app.post("/api/lesson/<int:lesson_id>/complete")
def api_lesson_complete(lesson_id: int):
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        return jsonify({"ok": False, "message": "Curso não liberado."}), 403
    payload = request.get_json(silent=True) or request.form
    answer = (payload.get("answer") or "").strip()
    ok, message, data = complete_lesson_exercise(user["id"], lesson_id, answer)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "message": message, **data}), status


@app.get("/api/journey/progress")
def api_journey_progress():
    login_redirect = require_login(request.path)
    if login_redirect:
        return login_redirect
    user = current_user()
    if not has_confirmed_product(user["id"], "escola-de-profetas"):
        return jsonify({"ok": False, "message": "Curso não liberado."}), 403
    return jsonify(get_journey_progress(user["id"]))



def admin_dashboard_context() -> dict[str, Any]:
    month_start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(DATE_FORMAT)
    week_start = (now() - timedelta(days=7)).strftime(DATE_FORMAT)
    total_users = query_one("SELECT COUNT(*) AS total FROM users")["total"]
    online_total = count_online_users()
    active_students = query_one("SELECT COUNT(DISTINCT user_id) AS total FROM enrollments WHERE status = 'active'")["total"]
    without_access = query_one(
        """
        SELECT COUNT(*) AS total
        FROM users u
        WHERE u.role != 'admin'
          AND NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.user_id = u.id AND e.status = 'active')
        """
    )["total"]
    paid_purchases = query_one("SELECT COUNT(*) AS total FROM purchases WHERE status = 'paid'")["total"]
    total_revenue = query_one("SELECT COALESCE(SUM(amount_cents), 0) AS total FROM purchases WHERE status = 'paid'")["total"]
    month_revenue = query_one("SELECT COALESCE(SUM(amount_cents), 0) AS total FROM purchases WHERE status = 'paid' AND confirmed_at >= ?", (month_start,))["total"]
    week_revenue = query_one("SELECT COALESCE(SUM(amount_cents), 0) AS total FROM purchases WHERE status = 'paid' AND confirmed_at >= ?", (week_start,))["total"]
    pending_purchases = query_one("SELECT COUNT(*) AS total FROM purchases WHERE status = 'pending'")["total"]
    canceled_purchases = query_one("SELECT COUNT(*) AS total FROM purchases WHERE status IN ('canceled', 'refunded')")["total"]
    recent_comments_count = query_one("SELECT COUNT(*) AS total FROM course_comments WHERE created_at >= ?", (week_start,))["total"]
    average_ticket = int(total_revenue / paid_purchases) if paid_purchases else 0

    online_users = get_online_users()
    funnel = build_admin_funnel(total_users)
    course_status = build_course_status_rows()
    cycle_status = build_cycle_status_rows()
    finance_rows = get_admin_purchase_rows(limit=8)
    progress_rows = get_admin_progress_rows(limit=10)
    recent_comments = get_admin_comment_rows(limit=6)

    cards = [
        {"label": "Usuários cadastrados", "value": total_users, "hint": "Total no banco"},
        {"label": "Online agora", "value": online_total, "hint": "Últimos 5 minutos"},
        {"label": "Alunos com acesso ativo", "value": active_students, "hint": "Matrículas active"},
        {"label": "Sem acesso ativo", "value": without_access, "hint": "Alunos sem matrícula"},
        {"label": "Vendas confirmadas", "value": paid_purchases, "hint": "Compras paid"},
        {"label": "Receita total", "value": money_from_cents(total_revenue), "hint": "Compras pagas"},
        {"label": "Receita do mês", "value": money_from_cents(month_revenue), "hint": "Mês atual"},
        {"label": "Compras pendentes", "value": pending_purchases, "hint": "Status pending"},
        {"label": "Canceladas/reembolsadas", "value": canceled_purchases, "hint": "Status canceled/refunded"},
        {"label": "Comentários recentes", "value": recent_comments_count, "hint": "Últimos 7 dias"},
    ]
    finance = {
        "total": money_from_cents(total_revenue),
        "month": money_from_cents(month_revenue),
        "week": money_from_cents(week_revenue),
        "ticket": money_from_cents(average_ticket),
        "paid": paid_purchases,
        "pending": pending_purchases,
        "canceled": query_one("SELECT COUNT(*) AS total FROM purchases WHERE status = 'canceled'")["total"],
        "refunded": query_one("SELECT COUNT(*) AS total FROM purchases WHERE status = 'refunded'")["total"],
    }
    return {
        "cards": cards,
        "online_users": online_users,
        "funnel": funnel,
        "course_status": course_status,
        "cycle_status": cycle_status,
        "finance": finance,
        "finance_rows": finance_rows,
        "progress_rows": progress_rows,
        "recent_comments": recent_comments,
    }


def build_admin_funnel(total_users: int) -> list[dict[str, Any]]:
    rows = [
        ("Visitantes cadastrados", total_users),
        ("Compra pendente", query_one("SELECT COUNT(DISTINCT user_id) AS total FROM purchases WHERE status = 'pending'")["total"]),
        ("Pagamento confirmado", query_one("SELECT COUNT(DISTINCT user_id) AS total FROM purchases WHERE status = 'paid'")["total"]),
        ("Curso liberado", query_one("SELECT COUNT(DISTINCT user_id) AS total FROM enrollments WHERE status = 'active'")["total"]),
        ("Iniciaram o curso", query_one("SELECT COUNT(DISTINCT user_id) AS total FROM course_progress WHERE status IN ('em_andamento', 'concluido')")["total"]),
        ("Concluíram 1 aula", query_one("SELECT COUNT(DISTINCT user_id) AS total FROM course_progress WHERE status = 'concluido'")["total"]),
    ]
    completed_all = 0
    for user_row in query_all("SELECT id FROM users WHERE role != 'admin'"):
        progress = calculate_user_course_progress(user_row["id"], "escola-de-profetas")
        if progress["total"] and progress["percent"] == 100:
            completed_all += 1
    rows.append(("Concluíram todos os conteúdos", completed_all))
    base = total_users or 1
    return [{"label": label, "value": value, "percent": int((value / base) * 100)} for label, value in rows]


def build_course_status_rows() -> list[dict[str, Any]]:
    rows = []
    for course in query_all("SELECT * FROM courses ORDER BY title"):
        active = query_one("SELECT COUNT(*) AS total FROM enrollments WHERE course_id = ? AND status = 'active'", (course["id"],))["total"]
        blocked = query_one("SELECT COUNT(*) AS total FROM enrollments WHERE course_id = ? AND status != 'active'", (course["id"],))["total"]
        pending = query_one("SELECT COUNT(*) AS total FROM purchases WHERE course_id = ? AND status = 'pending'", (course["id"],))["total"]
        paid = query_one("SELECT COUNT(*) AS total FROM purchases WHERE course_id = ? AND status = 'paid'", (course["id"],))["total"]
        revenue = query_one("SELECT COALESCE(SUM(amount_cents), 0) AS total FROM purchases WHERE course_id = ? AND status = 'paid'", (course["id"],))["total"]
        progress_values = [calculate_user_course_progress(row["user_id"], course["slug"])["percent"] for row in query_all("SELECT user_id FROM enrollments WHERE course_id = ? AND status = 'active'", (course["id"],))]
        average_progress = int(sum(progress_values) / len(progress_values)) if progress_values else 0
        rows.append({"course": course, "active": active, "blocked": blocked, "pending": pending, "paid": paid, "revenue": money_from_cents(revenue), "average_progress": average_progress})
    return rows


def build_cycle_status_rows() -> list[dict[str, Any]]:
    active_users = query_all(
        """
        SELECT DISTINCT e.user_id
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        WHERE c.slug = 'escola-de-profetas' AND e.status = 'active'
        """
    )
    rows = []
    for cycle in COURSE_CYCLES.values():
        progress_values = []
        started = one_done = completed = 0
        for user_row in active_users:
            progress = calculate_cycle_progress(user_row["user_id"], "escola-de-profetas", cycle["slug"])
            progress_values.append(progress["percent"])
            started += int(query_one("SELECT COUNT(*) AS total FROM course_progress WHERE user_id = ? AND cycle_slug = ?", (user_row["user_id"], cycle["slug"]))["total"] > 0)
            one_done += int(progress["done"] > 0)
            completed += int(progress["total"] > 0 and progress["done"] == progress["total"])
        average = int(sum(progress_values) / len(progress_values)) if progress_values else 0
        rows.append({"cycle": cycle, "started": started, "one_done": one_done, "completed": completed, "average": average})
    return rows


def get_admin_purchase_rows(limit: int | None = None) -> list[sqlite3.Row]:
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    return query_all(
        f"""
        SELECT p.*, u.name AS user_name, u.email, c.title AS course_title, c.slug AS course_slug
        FROM purchases p
        JOIN users u ON u.id = p.user_id
        JOIN courses c ON c.id = p.course_id
        ORDER BY p.created_at DESC
        {limit_sql}
        """
    )


def get_admin_progress_rows(limit: int | None = None) -> list[dict[str, Any]]:
    users = query_all(
        """
        SELECT u.*, e.status AS enrollment_status, c.slug AS course_slug, c.title AS course_title
        FROM users u
        LEFT JOIN enrollments e ON e.user_id = u.id
        LEFT JOIN courses c ON c.id = e.course_id
        WHERE u.role != 'admin'
        ORDER BY COALESCE(u.last_seen_at, u.created_at) DESC
        """
    )
    rows = []
    for user_row in users:
        course_slug = user_row["course_slug"] or "escola-de-profetas"
        progress = calculate_user_course_progress(user_row["id"], course_slug)
        status = "sem compra ativa"
        if user_row["enrollment_status"] == "active":
            status = "concluiu" if progress["percent"] == 100 else ("em andamento" if progress["done"] else "não iniciou")
        elif user_row["enrollment_status"]:
            status = "acesso bloqueado"
        rows.append({"user": user_row, "course": user_row["course_title"] or "Escola de Profetas", "cycle": current_cycle_for_user(user_row["id"]), "progress": progress, "status": status})
    return rows[:limit] if limit else rows


def get_admin_comment_rows(limit: int | None = None, cycle_filter: str = "", user_filter: str = "") -> list[dict[str, Any]]:
    conditions = []
    params: list[Any] = []
    if cycle_filter in COURSE_CYCLES:
        conditions.append("c.cycle_slug = ?")
        params.append(cycle_filter)
    if user_filter:
        conditions.append("(u.name LIKE ? OR u.email LIKE ?)")
        params.extend([f"%{user_filter}%", f"%{user_filter}%"])
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    comments = query_all(
        f"""
        SELECT c.*, u.name AS user_name, u.email, p.status
        FROM course_comments c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN course_progress p
+          ON p.user_id = c.user_id AND p.cycle_slug = c.cycle_slug AND p.content_slug = c.content_slug
        {where}
        ORDER BY c.updated_at DESC
        {limit_sql}
        """.replace("\n+", "\n"),
        tuple(params),
    )
    rows = []
    for row in comments:
        rows.append({"row": row, "cycle": course_cycle_by_slug(row["cycle_slug"]), "content": course_content_by_slug(row["cycle_slug"], row["content_slug"])})
    return rows


@app.route("/admin")
@admin_required
def admin():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/dashboard", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    if request.method == "POST":
        question_id = int(request.form.get("question_id", "0"))
        answer = request.form.get("answer", "").strip()
        status = request.form.get("status", "respondida")
        sensitive = 1 if request.form.get("is_sensitive") else 0
        if question_id and answer:
            execute(
                "UPDATE questions_channel SET answer = ?, status = ?, is_sensitive = ?, answered_at = ? WHERE id = ?",
                (answer, status, sensitive, now_str(), question_id),
            )
            flash("Dúvida atualizada no painel privado.", "success")
            return redirect(url_for("admin_dashboard"))
    update_presence(current_user()["id"], request.path)
    log_activity("abriu painel admin")
    return render_template("admin/dashboard.html", **admin_dashboard_context())


@app.route("/admin/estacoes")
@admin_required
def admin_stations():
    rows = []
    for user_row in query_all("SELECT * FROM users ORDER BY name"):
        initialize_station_progress_for_user(user_row["id"])
        current = get_user_current_station(user_row["id"])
        current_lesson = None
        if current:
            current_lesson = query_one(
                """
                SELECT l.*, p.status
                FROM station_lessons l
                JOIN user_lesson_progress p ON p.lesson_id = l.id AND p.user_id = ?
                WHERE l.station_id = ? AND p.status IN ('liberada', 'audio_ouvido', 'exercicio_iniciado')
                ORDER BY l.lesson_order
                LIMIT 1
                """,
                (user_row["id"], current["id"]),
            )
        last_done = query_one("SELECT MAX(completed_at) AS last_done FROM user_lesson_progress WHERE user_id = ? AND completed_at IS NOT NULL", (user_row["id"],))["last_done"]
        station_progress = get_station_progress(user_row["id"], current["id"]) if current else {"percent": 0}
        status = "Em dia"
        if last_done:
            status = "Em dia" if now() - parse_dt(last_done) <= timedelta(days=7) else "Parado"
        if station_progress["percent"] >= 70:
            status = "Avançando bem"
        rows.append({"user": user_row, "current": current, "lesson": current_lesson, "journey": get_journey_progress(user_row["id"]), "station_progress": station_progress, "last_done": last_done or "Sem conclusão", "status": status})
    return render_template("admin_stations.html", rows=rows)


@app.route("/admin/comentarios")
@admin_required
def admin_course_comments():
    cycle_filter = request.args.get("cycle") or ""
    user_filter = request.args.get("q") or ""
    rows = get_admin_comment_rows(cycle_filter=cycle_filter, user_filter=user_filter)
    log_activity("abriu admin comentarios")
    return render_template("admin/comentarios.html", rows=rows, cycles=COURSE_CYCLES.values(), cycle_filter=cycle_filter, user_filter=user_filter)


@app.route("/admin/alunos")
@admin_required
def admin_alunos():
    q = (request.args.get("q") or "").strip()
    status_filter = request.args.get("status") or ""
    conditions = []
    params: list[Any] = []
    if q:
        conditions.append("(u.name LIKE ? OR u.email LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if status_filter == "admin":
        conditions.append("u.role = 'admin'")
    elif status_filter == "student":
        conditions.append("u.role != 'admin'")
    elif status_filter == "online":
        conditions.append("COALESCE(u.last_seen_at, '') >= ?")
        params.append(online_cutoff())
    elif status_filter == "offline":
        conditions.append("(u.last_seen_at IS NULL OR u.last_seen_at < ?)")
        params.append(online_cutoff())
    elif status_filter == "com_acesso":
        conditions.append("EXISTS (SELECT 1 FROM enrollments e WHERE e.user_id = u.id AND e.status = 'active')")
    elif status_filter == "sem_acesso":
        conditions.append("NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.user_id = u.id AND e.status = 'active')")
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    users = query_all(f"SELECT u.* FROM users u {where} ORDER BY u.created_at DESC", tuple(params))
    rows = []
    for user_row in users:
        courses = query_all(
            """
            SELECT c.title, e.status
            FROM enrollments e
            JOIN courses c ON c.id = e.course_id
            WHERE e.user_id = ?
            ORDER BY c.title
            """,
            (user_row["id"],),
        )
        active_courses = ", ".join(row["title"] for row in courses if row["status"] == "active")
        is_online = bool(user_row["last_seen_at"] and user_row["last_seen_at"] >= online_cutoff())
        rows.append({"user": user_row, "courses": courses, "active_courses": active_courses, "is_online": is_online, "progress": calculate_user_course_progress(user_row["id"], "escola-de-profetas")})
    return render_template("admin/alunos.html", rows=rows, q=q, status_filter=status_filter)


@app.route("/admin/aluno/<int:user_id>")
@admin_required
def admin_aluno_detalhe(user_id: int):
    user_row = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user_row:
        abort(404)
    purchases = query_all(
        """
        SELECT p.*, c.title AS course_title
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        """,
        (user_id,),
    )
    enrollments = query_all(
        """
        SELECT e.*, c.title AS course_title, c.slug AS course_slug
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        WHERE e.user_id = ?
        ORDER BY e.updated_at DESC
        """,
        (user_id,),
    )
    cycle_rows = [{"cycle": cycle, "progress": calculate_cycle_progress(user_id, "escola-de-profetas", cycle["slug"])} for cycle in COURSE_CYCLES.values()]
    comments = get_admin_comment_rows(user_filter=user_row["email"])
    return render_template("admin/aluno_detalhe.html", user_row=user_row, purchases=purchases, enrollments=enrollments, cycle_rows=cycle_rows, comments=comments)


@app.post("/admin/alunos/<int:user_id>/liberar")
@app.post("/admin/aluno/<int:user_id>/liberar-acesso")
@admin_required
def admin_liberar_acesso(user_id: int):
    course = get_course_by_slug("escola-de-profetas")
    activate_enrollment(user_id, course["id"])
    flash("Acesso liberado manualmente.", "success")
    return redirect(request.referrer or url_for("admin_alunos"))


@app.post("/admin/alunos/<int:user_id>/bloquear")
@app.post("/admin/aluno/<int:user_id>/bloquear-acesso")
@admin_required
def admin_bloquear_acesso(user_id: int):
    course = get_course_by_slug("escola-de-profetas")
    execute("UPDATE enrollments SET status = 'blocked', updated_at = ? WHERE user_id = ? AND course_id = ?", (now_str(), user_id, course["id"]))
    flash("Acesso bloqueado.", "success")
    return redirect(request.referrer or url_for("admin_alunos"))


@app.route("/admin/compras")
@admin_required
def admin_compras():
    status_filter = request.args.get("status") or ""
    course_filter = request.args.get("course") or ""
    conditions = []
    params: list[Any] = []
    if status_filter:
        conditions.append("p.status = ?")
        params.append(status_filter)
    if course_filter:
        conditions.append("c.slug = ?")
        params.append(course_filter)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = query_all(
        f"""
        SELECT p.*, u.name AS user_name, u.email, c.title AS course_title, c.slug AS course_slug
        FROM purchases p
        JOIN users u ON u.id = p.user_id
        JOIN courses c ON c.id = p.course_id
        {where}
        ORDER BY p.created_at DESC
        """,
        tuple(params),
    )
    courses = query_all("SELECT * FROM courses ORDER BY title")
    return render_template("admin/compras.html", rows=rows, courses=courses, status_filter=status_filter, course_filter=course_filter)


@app.post("/admin/compras/<int:purchase_id>/marcar-pago")
@app.post("/admin/compra/<int:purchase_id>/marcar-pago")
@admin_required
def admin_marcar_compra_paga(purchase_id: int):
    purchase = mark_purchase_paid_by_id(purchase_id)
    if purchase:
        flash("Compra marcada como paga e acesso liberado.", "success")
    return redirect(request.referrer or url_for("admin_compras"))


@app.post("/admin/compra/<int:purchase_id>/cancelar")
@admin_required
def admin_cancelar_compra(purchase_id: int):
    purchase = query_one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))
    if not purchase:
        abort(404)
    execute("UPDATE purchases SET status = 'canceled', updated_at = ? WHERE id = ?", (now_str(), purchase_id))
    execute("UPDATE enrollments SET status = 'blocked', updated_at = ? WHERE user_id = ? AND course_id = ?", (now_str(), purchase["user_id"], purchase["course_id"]))
    flash("Compra cancelada e acesso bloqueado, quando existente.", "success")
    return redirect(request.referrer or url_for("admin_compras"))


@app.route("/admin/relatorios")
@admin_required
def admin_relatorios():
    return render_template("admin/relatorios.html")


@app.get("/admin/exportar/alunos")
@admin_required
def admin_exportar_alunos():
    rows = []
    for user_row in query_all("SELECT * FROM users ORDER BY id"):
        courses = query_all(
            """
            SELECT c.title
            FROM enrollments e
            JOIN courses c ON c.id = e.course_id
            WHERE e.user_id = ? AND e.status = 'active'
            ORDER BY c.title
            """,
            (user_row["id"],),
        )
        online = "online" if user_row["last_seen_at"] and user_row["last_seen_at"] >= online_cutoff() else "offline"
        rows.append([user_row["id"], user_row["name"], user_row["email"], user_row["role"], user_row["created_at"], user_row["last_seen_at"] or "", online, ", ".join(row["title"] for row in courses)])
    return csv_response("alunos.csv", ["id", "nome", "email", "role", "created_at", "ultimo_acesso", "status_online", "cursos_ativos"], rows)


@app.get("/admin/exportar/compras")
@admin_required
def admin_exportar_compras():
    rows = [[row["id"], row["user_name"], row["email"], row["course_title"], row["status"], money_from_cents(row["amount_cents"]), row["payment_provider"] or "", row["payment_reference"] or "", row["created_at"], row["confirmed_at"] or ""] for row in get_admin_purchase_rows()]
    return csv_response("compras.csv", ["id", "usuario", "email", "curso", "status", "valor", "provider", "reference", "created_at", "confirmed_at"], rows)


@app.get("/admin/exportar/progresso")
@admin_required
def admin_exportar_progresso():
    rows = []
    progress_rows = query_all(
        """
        SELECT cp.*, u.name AS user_name, u.email
        FROM course_progress cp
        JOIN users u ON u.id = cp.user_id
        ORDER BY u.name, cp.cycle_slug, cp.content_slug
        """
    )
    for row in progress_rows:
        rows.append([row["user_name"], row["email"], row["course_slug"], row["cycle_slug"], row["content_slug"], row["status"], row["completed_at"] or "", row["updated_at"]])
    return csv_response("progresso.csv", ["usuario", "email", "curso", "ciclo", "conteudo", "status", "completed_at", "updated_at"], rows)


@app.get("/admin/exportar/comentarios")
@admin_required
def admin_exportar_comentarios():
    rows = []
    for item in get_admin_comment_rows():
        row = item["row"]
        rows.append([row["user_name"], row["email"], row["course_slug"], row["cycle_slug"], row["content_slug"], row["comment_text"], row["created_at"]])
    return csv_response("comentarios.csv", ["usuario", "email", "curso", "ciclo", "conteudo", "comentario", "created_at"], rows)


@app.post("/api/ping")
def api_ping():
    user = current_user()
    if user is None:
        return jsonify({"ok": False, "authenticated": False}), 401
    payload = request.get_json(silent=True) or {}
    page = payload.get("page") or request.headers.get("Referer") or request.path
    execute("UPDATE users SET last_seen_at = ?, current_page = ? WHERE id = ?", (now_str(), page, user["id"]))
    execute("INSERT INTO activity_log (user_id, action, page, created_at) VALUES (?, 'ping online', ?, ?)", (user["id"], page, now_str()))
    return jsonify({"ok": True, "last_seen_at": now_str()})


init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

# DEPLOY_TIMESTAMP: 2026-10-16T16:47:41.110649
#!/usr/bin/env python3
import os
import json
import random
import hashlib
import sqlite3
import datetime
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(DATA_DIR, "dm_varejo.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

TODAY_STR = "2026-10-14"
TODAY_DATE = datetime.date(2026, 10, 14)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_store_settings(conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cur = conn.cursor()
    cur.execute("SELECT * FROM store_settings WHERE id = 1")
    row = cur.fetchone()
    if close_after:
        conn.close()
    if row:
        return dict(row)
    return {
        "id": 1,
        "store_name": "Armarinhos Fernando Ltda.",
        "card_brand_name": "Cartão Armarinhos Fernando",
        "cnpj": "24.890.100/0001-60",
        "pix_key": "faturas@armarinhosfernando.com.br",
        "support_whatsapp": "5511980005544",
        "anuidade_faturada_brl": 14.90,
        "seguro_protegido_brl": 9.90,
        "sms_alerta_brl": 5.90,
        "fine_pct": 2.0,
        "rotativo_interest_pct": 11.9,
        "crediario_interest_pct": 4.99,
        "parcelado_fatura_pct": 6.9,
        "comissao_promotor_brl": 6.00,
        "comissao_seguro_brl": 3.50,
        "min_score_auto_approve": 550,
        "auto_block_days": 5,
        "first_purchase_discount_pct": 10.0,
        "brand_color": "#d4af37",
    }


def compute_best_purchase_day(due_day):
    due_day = int(due_day or 10)
    best = due_day - 9
    if best <= 0:
        best += 30
    return best


def calculate_days_overdue(due_date_str, ref_date=TODAY_DATE):
    try:
        y, m, d = map(int, due_date_str.split("-"))
        due = datetime.date(y, m, d)
        return (ref_date - due).days
    except Exception:
        return 0


def calculate_statement_amounts(original_amount, days_overdue, fine_pct=2.0, rotativo_monthly_pct=11.9):
    min_payment = round(max(25.0, original_amount * 0.15), 2)
    if min_payment > original_amount:
        min_payment = round(original_amount, 2)
    if days_overdue <= 0:
        return {
            "original_amount": round(original_amount, 2),
            "minimum_payment": min_payment,
            "days_overdue": days_overdue,
            "fine_amount": 0.0,
            "interest_amount": 0.0,
            "total_charges": 0.0,
            "updated_amount": round(original_amount, 2),
        }
    fine_amount = original_amount * (fine_pct / 100.0)
    daily_rate = (rotativo_monthly_pct / 100.0) / 30.0
    interest_amount = original_amount * daily_rate * days_overdue
    total_charges = fine_amount + interest_amount
    updated_amount = original_amount + total_charges
    return {
        "original_amount": round(original_amount, 2),
        "minimum_payment": min_payment,
        "days_overdue": days_overdue,
        "fine_amount": round(fine_amount, 2),
        "interest_amount": round(interest_amount, 2),
        "total_charges": round(total_charges, 2),
        "updated_amount": round(updated_amount, 2),
    }


def suggest_credit_limit(income, score):
    if score < 440:
        return 0.0, "Recusado Política"
    elif score < 560:
        return round(max(400.0, income * 0.22), -1), "Private Label Loja"
    elif score < 740:
        return round(max(800.0, income * 0.38), -1), "Gold Mais"
    else:
        return round(max(1600.0, income * 0.60), -1), "VIP Internacional"


def generate_qr_svg(payload_text, size=168):
    digest = hashlib.sha256(payload_text.encode("utf-8")).digest()
    grid_n = 21
    cell = size // grid_n
    rects = []

    def finder_pixel(r, c, r0, c0):
        lr, lc = r - r0, c - c0
        if lr in (0, 6) or lc in (0, 6):
            return True
        if 2 <= lr <= 4 and 2 <= lc <= 4:
            return True
        return False

    bit_idx = 0
    for r in range(grid_n):
        for c in range(grid_n):
            fill = False
            if r < 7 and c < 7:
                fill = finder_pixel(r, c, 0, 0)
            elif r < 7 and c >= grid_n - 7:
                fill = finder_pixel(r, c, 0, grid_n - 7)
            elif r >= grid_n - 7 and c < 7:
                fill = finder_pixel(r, c, grid_n - 7, 0)
            else:
                byte_val = digest[(bit_idx // 8) % len(digest)]
                fill = bool((byte_val >> (bit_idx % 8)) & 1)
                bit_idx += 1

            if fill:
                x = c * cell
                y = r * cell
                rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="#0f172a"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {grid_n * cell} {grid_n * cell}" '
        f'width="{size}" height="{size}" style="background:#fff; padding:8px; border-radius:10px; border:1px solid #cbd5e1;">'
        + "".join(rects)
        + "</svg>"
    )


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS store_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            store_name TEXT NOT NULL,
            card_brand_name TEXT NOT NULL,
            cnpj TEXT NOT NULL,
            pix_key TEXT NOT NULL,
            support_whatsapp TEXT NOT NULL,
            anuidade_faturada_brl REAL DEFAULT 14.90,
            seguro_protegido_brl REAL DEFAULT 9.90,
            sms_alerta_brl REAL DEFAULT 5.90,
            fine_pct REAL DEFAULT 2.0,
            rotativo_interest_pct REAL DEFAULT 11.9,
            crediario_interest_pct REAL DEFAULT 4.99,
            parcelado_fatura_pct REAL DEFAULT 6.9,
            comissao_promotor_brl REAL DEFAULT 6.00,
            comissao_seguro_brl REAL DEFAULT 3.50,
            min_score_auto_approve INTEGER DEFAULT 550,
            auto_block_days INTEGER DEFAULT 5,
            first_purchase_discount_pct REAL DEFAULT 10.0,
            brand_color TEXT DEFAULT '#d4af37'
        )
    """)

    cur.execute("SELECT COUNT(*) as c FROM store_settings")
    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO store_settings (
                id, store_name, card_brand_name, cnpj, pix_key, support_whatsapp,
                anuidade_faturada_brl, seguro_protegido_brl, sms_alerta_brl,
                fine_pct, rotativo_interest_pct, crediario_interest_pct, parcelado_fatura_pct,
                comissao_promotor_brl, comissao_seguro_brl, min_score_auto_approve,
                auto_block_days, first_purchase_discount_pct, brand_color
            ) VALUES (
                1,
                'Armarinhos Fernando Ltda.',
                'Cartão Armarinhos Fernando',
                '24.890.100/0001-60',
                'faturas@armarinhosfernando.com.br',
                '5511980005544',
                14.90, 9.90, 5.90,
                2.0, 11.9, 4.99, 6.9,
                6.00, 3.50, 550,
                5, 10.0, '#d4af37'
            )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_holders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            cpf TEXT NOT NULL,
            rg_cnh TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            mother_name TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            email TEXT NOT NULL,
            occupation TEXT NOT NULL,
            declared_income REAL NOT NULL,
            store_branch TEXT NOT NULL,
            promoter_name TEXT NOT NULL,
            credit_score INTEGER NOT NULL,
            biometria_status TEXT NOT NULL DEFAULT 'Validada (99.2% FaceMatch)',
            doc_status TEXT NOT NULL DEFAULT 'RG/CNH Frente/Verso OK',
            otp_verified INTEGER DEFAULT 1,
            lead_stage TEXT NOT NULL DEFAULT 'novo_lead',
            approved_limit REAL DEFAULT 0.0,
            used_limit REAL DEFAULT 0.0,
            card_number_full TEXT NOT NULL,
            card_number_last4 TEXT NOT NULL,
            card_cvv TEXT NOT NULL,
            card_expiry TEXT NOT NULL,
            card_pin TEXT NOT NULL DEFAULT '1234',
            card_tier TEXT DEFAULT 'Private Label Loja',
            due_day INTEGER DEFAULT 10,
            best_purchase_day INTEGER DEFAULT 1,
            has_seguro_protegido INTEGER DEFAULT 1,
            has_sms_alerta INTEGER DEFAULT 1,
            first_purchase_done INTEGER DEFAULT 0,
            voucher_code TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pos_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nsu_code TEXT NOT NULL,
            holder_id INTEGER NOT NULL,
            store_branch TEXT NOT NULL,
            cashier_name TEXT NOT NULL,
            modality TEXT NOT NULL,
            items_description TEXT NOT NULL,
            gross_amount REAL NOT NULL,
            total_with_interest REAL NOT NULL,
            installments INTEGER NOT NULL,
            installment_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'APROVADA',
            created_at TEXT NOT NULL,
            FOREIGN KEY (holder_id) REFERENCES card_holders(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_code TEXT NOT NULL,
            holder_id INTEGER NOT NULL,
            reference_month TEXT NOT NULL,
            items_summary TEXT NOT NULL,
            purchases_amount REAL NOT NULL,
            fees_and_insurance_amount REAL NOT NULL DEFAULT 24.80,
            original_amount REAL NOT NULL,
            closing_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'aberta',
            paid_date TEXT DEFAULT NULL,
            paid_amount REAL DEFAULT NULL,
            promise_date TEXT DEFAULT NULL,
            promise_note TEXT DEFAULT NULL,
            pix_key TEXT DEFAULT '00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br5204000053039865802BR',
            digitable_line TEXT DEFAULT '23793.38128 60084.219018 27391.100009 8 98700000048000',
            last_contact_at TEXT DEFAULT NULL,
            last_stage_sent TEXT DEFAULT NULL,
            contact_count INTEGER DEFAULT 0,
            FOREIGN KEY (holder_id) REFERENCES card_holders(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS collection_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_offset INTEGER NOT NULL,
            stage_code TEXT NOT NULL,
            title TEXT NOT NULL,
            channel TEXT NOT NULL,
            tone TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            subject_template TEXT NOT NULL,
            message_template TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS interaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id INTEGER DEFAULT NULL,
            holder_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            stage_code TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message_body TEXT NOT NULL,
            outcome TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_agreements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agreement_code TEXT NOT NULL,
            statement_id INTEGER NOT NULL,
            holder_id INTEGER NOT NULL,
            original_amount REAL NOT NULL,
            updated_amount REAL NOT NULL,
            discount_pct REAL NOT NULL,
            final_amount REAL NOT NULL,
            installments INTEGER NOT NULL,
            down_payment REAL NOT NULL,
            installment_value REAL NOT NULL,
            first_due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Ativo',
            signer_name TEXT DEFAULT NULL,
            signer_cpf TEXT DEFAULT NULL,
            signer_ip TEXT DEFAULT NULL,
            signature_hash TEXT DEFAULT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            cpf TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cobranca',
            department TEXT NOT NULL DEFAULT 'Setor de Cobrança',
            branch TEXT NOT NULL DEFAULT 'Matriz Centro',
            status TEXT NOT NULL DEFAULT 'ativo',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("SELECT COUNT(*) as c FROM admin_users")
    if cur.fetchone()["c"] == 0:
        cur.executemany("""
            INSERT INTO admin_users (full_name, cpf, password, role, department, branch, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("Pedro Henrique Anjo", "388.776.368-82", "2030", "adm_geral", "Diretoria / Adm Geral", "Matriz Centro", "ativo", "2026-10-15 10:00"),
            ("Carlos Eduardo Silva", "111.111.111-11", "1234", "adm_geral", "Administração Geral Master", "Matriz Centro", "ativo", "2026-10-15 10:05"),
            ("Fernanda Lima", "222.222.222-22", "1234", "credito", "Mesa de Crédito & Limites", "Matriz Centro", "ativo", "2026-10-15 10:10"),
            ("Marcos Vinícius Souza", "333.333.333-33", "1234", "cobranca", "Central de Cobrança & Acordos", "Matriz Centro", "ativo", "2026-10-15 10:15"),
        ])

    cur.execute("SELECT COUNT(*) as c FROM card_holders")
    if cur.fetchone()["c"] == 0:
        seed_dm_data(cur)

    # Garantir que todas as informações da loja estejam atualizadas para Armarinhos Fernando
    cur.execute("""
        UPDATE store_settings
        SET store_name = 'Armarinhos Fernando Ltda.',
            card_brand_name = 'Cartão Armarinhos Fernando',
            pix_key = 'faturas@armarinhosfernando.com.br'
        WHERE id = 1
    """)
    cur.execute("UPDATE card_holders SET voucher_code = replace(voucher_code, '-BP', '-AF')")

    # Garantir que o cliente Pedro Henrique Anjo esteja sempre cadastrado mesmo em deploy novo
    cur.execute("SELECT id FROM card_holders WHERE replace(replace(cpf, '.', ''), '-', '') = '38877636882'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO card_holders (
              full_name, cpf, rg_cnh, birth_date, mother_name, whatsapp, email,
              occupation, declared_income, store_branch, promoter_name, credit_score,
              biometria_status, doc_status, otp_verified, lead_stage,
              approved_limit, used_limit, card_number_full, card_number_last4,
              card_cvv, card_expiry, card_pin, card_tier, due_day, best_purchase_day,
              has_seguro_protegido, has_sms_alerta, first_purchase_done, voucher_code,
              notes, created_at
            ) VALUES (
              'Pedro Henrique Anjo', '388.776.368-82', '49.382.110-7 SSP/SP', '1996-03-14',
              'Ana Paula Anjo', '5511997763688', 'pedro.anjo@primevip.com.br',
              'Empresário / Executivo', 12500.0, 'Matriz 25 de Março', 'Vanessa (Consultora Prime)',
              845, 'Validada (99.8% FaceMatch)', 'CNH Digital Validada', 1, 'ativo_faturado',
              4000.0, 0.0, '6060 8421 9020 3682', '3682', '779', '10/2031', '2030',
              'VIP Internacional', 15, 5, 1, 1, 0, 'VCH-3682-VIP',
              'Cliente VIP Internacional aprovado pela consultora com R$ 4.000,00 de limite.',
              '2026-10-15 16:30'
            )
        """)
        pedro_id = cur.lastrowid
        cur.execute("""
            INSERT INTO card_statements (
              statement_code, holder_id, reference_month, items_summary,
              purchases_amount, fees_and_insurance_amount, original_amount,
              closing_date, due_date, status, pix_key, digitable_line, contact_count
            ) VALUES (
              ?, ?, 'Outubro/2026', 'Ciclo Aberto VIP Internacional (Limite R$ 4.000,00 Disponível)',
              0.0, 0.0, 0.0, '2026-11-05', '2026-11-15', 'paga',
              '00020126580014BR.GOV.BCB.PIX0114388776368825204000053039865802BR',
              '60609.00015 00842.190204 36820.100008 1 99120000000000', 0
            )
        """, (f"FAT-2026-{pedro_id:03d}", pedro_id))

    conn.commit()
    conn.close()


def seed_dm_data(cur):
    holders = [
        # 1. Na Mesa de Crédito / Biometria no Balcão da Loja
        (
            "Camila Ferreira dos Santos",
            "384.912.048-22",
            "44.819.201-X SSP/SP",
            "1994-06-18",
            "Maria Helena Ferreira",
            "5511988124401",
            "camila.santos94@gmail.com",
            "Técnica de Enfermagem",
            4200.00,
            "Matriz 25 de Março",
            "Vanessa (Consultora Prime)",
            685,
            "Validada (99.4% FaceMatch)",
            "CNH Digital Validada",
            1,
            "mesa_credito",
            1500.00,
            0.0,
            "6060 8421 3910 7391",
            "7391",
            "418",
            "10/2031",
            "4455",
            "Gold Mais",
            15,
            6,
            1,
            1,
            0,
            "VCH-7391-BP",
            "Cliente no balcão com carrinho de R$ 480 aguardando emissão do Voucher de 1ª Compra.",
            "2026-10-14 14:10"
        ),
        # 2. Aprovado c/ Voucher Emitido (Falta passar no Caixa para 1ª Compra)
        (
            "Lucas Gabriel Oliveira",
            "419.203.881-05",
            "39.104.882-1 SSP/SP",
            "1998-11-03",
            "Sônia Aparecida Oliveira",
            "5511974208819",
            "lucas.oliveira@outlook.com",
            "Conferente de Logística",
            3100.00,
            "Filial Brás",
            "Rodrigo (Consultor Prime)",
            620,
            "Validada (98.7% FaceMatch)",
            "RG Frente/Verso OK",
            1,
            "aprovado_sem_compra",
            1100.00,
            0.0,
            "6060 8421 7741 9042",
            "9042",
            "902",
            "10/2031",
            "1020",
            "Private Label Loja",
            10,
            1,
            1,
            1,
            0,
            "VCH-9042-BP",
            "Voucher VCH-9042-BP emitido ontem. Acionar no WhatsApp para usar os 10% OFF na 1ª compra!",
            "2026-10-13 17:40"
        ),
        # 3. Portadora Bloqueada por Atraso Crítico (39 dias -> Fatura Setembro)
        (
            "Renata Cristina Almeida",
            "291.440.118-90",
            "28.501.339-4 SSP/SP",
            "1987-03-25",
            "Vera Lúcia Almeida",
            "5511991045520",
            "renata.almeida@uol.com.br",
            "Vendedora Autônoma",
            5400.00,
            "Matriz 25 de Março",
            "Vanessa (Consultora Prime)",
            430,
            "Validada (99.1% FaceMatch)",
            "RG Frente/Verso OK",
            1,
            "bloqueado_atraso",
            2000.00,
            1010.70,
            "6060 8421 1120 5518",
            "5518",
            "771",
            "04/2031",
            "8899",
            "Gold Mais",
            5,
            26,
            1,
            1,
            1,
            "VCH-5518-BP",
            "Cartão bloqueado no PDV (D+5). Quer parcelar a fatura em 6x no App para voltar a fazer compras do mês.",
            "2026-04-10 11:00"
        ),
        # 4. Portador Bloqueado Preventivamente (19 dias de atraso)
        (
            "Diego Henrique Martins",
            "332.890.441-12",
            "33.910.442-8 SSP/SP",
            "1991-08-14",
            "Cláudia Regina Martins",
            "5511977882310",
            "diego.martins@gmail.com",
            "Motorista de Aplicativo",
            3600.00,
            "Filial Brás",
            "Carla (Operadora Caixa 04)",
            510,
            "Validada (98.9% FaceMatch)",
            "CNH Validada",
            1,
            "bloqueado_atraso",
            1200.00,
            664.80,
            "6060 8421 6602 3310",
            "3310",
            "315",
            "05/2031",
            "2580",
            "Private Label Loja",
            25,
            16,
            1,
            0,
            1,
            "VCH-3310-BP",
            "Prometeu pagar via PIX na sexta-feira (16/10) para liberar o limite no fim de semana.",
            "2026-05-22 15:20"
        ),
        # 5. Portadora com Atraso Leve (4 dias -> ainda antes do bloqueio D+5)
        (
            "Juliana Mendes Costa",
            "405.118.920-66",
            "41.220.890-2 SSP/SP",
            "1995-01-30",
            "Rosângela Mendes",
            "5511996547712",
            "ju.mendes@gmail.com",
            "Professora Municipal",
            4800.00,
            "Matriz 25 de Março",
            "Rodrigo (Consultor Prime)",
            715,
            "Validada (99.5% FaceMatch)",
            "CNH Validada",
            1,
            "cartao_ativo",
            1800.00,
            544.80,
            "6060 8421 4490 8821",
            "8821",
            "604",
            "02/2031",
            "3690",
            "Gold Mais",
            10,
            1,
            1,
            1,
            1,
            "VCH-8821-BP",
            "Atraso de 4 dias. Se não pagar hoje, entra em bloqueio preventivo amanhã (D+5).",
            "2026-02-18 10:00"
        ),
        # 6. Portadora VIP Adimplente (Fatura vence Hoje 14/10)
        (
            "Patrícia Nogueira Souza",
            "218.774.309-44",
            "22.410.998-1 SSP/SP",
            "1983-09-12",
            "Teresa Nogueira Souza",
            "5511982331090",
            "patricia.nogueira@gmail.com",
            "Contadora Sênior",
            7800.00,
            "Matriz 25 de Março",
            "Vanessa (Consultora Prime)",
            890,
            "Validada (99.8% FaceMatch)",
            "CNH Digital Validada",
            1,
            "cartao_ativo",
            3500.00,
            980.00,
            "6060 8421 9901 1094",
            "1094",
            "991",
            "11/2030",
            "7788",
            "VIP Internacional",
            14,
            5,
            1,
            1,
            1,
            "VCH-1094-BP",
            "Cliente padrão ouro. Utiliza o cartão todo mês no supermercado e magazine.",
            "2025-11-05 16:00"
        ),
        # 7. Portador Ativo (Fatura Fechada vence dia 20/10)
        (
            "Marcos Vinícius Azevedo",
            "367.551.208-31",
            "35.881.204-5 SSP/SP",
            "1990-12-08",
            "Neusa Azevedo",
            "5511981193344",
            "marcos.azevedo@gmail.com",
            "Eletricista Industrial",
            4500.00,
            "Loja 03 - Shopping Norte",
            "Carla (Operadora Caixa 04)",
            795,
            "Validada (99.0% FaceMatch)",
            "RG Frente/Verso OK",
            1,
            "cartao_ativo",
            2200.00,
            454.80,
            "6060 8421 3319 6640",
            "6640",
            "512",
            "03/2031",
            "1478",
            "VIP Internacional",
            20,
            11,
            1,
            0,
            1,
            "VCH-6640-BP",
            "Fatura de Outubro fechada no corte do dia 11/10 e enviada por WhatsApp.",
            "2026-03-14 12:30"
        ),
        # 8. Novo Lead Captado no WhatsApp / Totem da Loja
        (
            "Beatriz Lima Rocha",
            "448.901.234-77",
            "48.902.114-3 SSP/SP",
            "2001-04-21",
            "Sandra Lima Rocha",
            "5511994410088",
            "bia.rocha01@gmail.com",
            "Manicure / MEI",
            2900.00,
            "Loja 03 - Shopping Norte",
            "Rodrigo (Consultor Prime)",
            605,
            "Validada (98.2% FaceMatch)",
            "CNH Digital Validada",
            1,
            "novo_lead",
            900.00,
            0.0,
            "6060 8421 5004 2198",
            "2198",
            "209",
            "10/2031",
            "9632",
            "Private Label Loja",
            10,
            1,
            1,
            1,
            0,
            "VCH-2198-BP",
            "Concluiu selfie e envio de CNH no celular há 10 minutos.",
            "2026-10-14 15:05"
        ),
    ]

    cur.executemany("""
        INSERT INTO card_holders (
            full_name, cpf, rg_cnh, birth_date, mother_name, whatsapp, email,
            occupation, declared_income, store_branch, promoter_name, credit_score,
            biometria_status, doc_status, otp_verified, lead_stage,
            approved_limit, used_limit, card_number_full, card_number_last4,
            card_cvv, card_expiry, card_pin, card_tier, due_day, best_purchase_day,
            has_seguro_protegido, has_sms_alerta, first_purchase_done, voucher_code,
            notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, holders)

    pos_txs = [
        ("NSU-901842", 3, "Matriz 25 de Março", "Caixa 02 - Juliana", "parcelado_sem_juros", "Compras Supermercado + Bazar (Parcela 2/4)", 980.00, 980.00, 4, 245.00, "APROVADA", "2026-08-18 16:40"),
        ("NSU-902119", 4, "Filial Brás", "Caixa 04 - Carla", "crediario_com_juros", "Eletroportáteis + Feira do Mês (3x)", 640.00, 640.00, 3, 213.33, "APROVADA", "2026-09-10 11:25"),
        ("NSU-904510", 5, "Matriz 25 de Março", "Caixa 01 - Marcos", "parcelado_sem_juros", "Moda & Calçados Coleção Primavera (3x)", 520.00, 520.00, 3, 173.33, "APROVADA", "2026-09-28 18:10"),
        ("NSU-905882", 6, "Matriz 25 de Março", "Caixa 02 - Juliana", "rotativo_vista", "Compras Hipermercado & Perfumaria (Vista 40 dias)", 949.30, 949.30, 1, 949.30, "APROVADA", "2026-10-02 14:50"),
        ("NSU-906104", 7, "Loja 03 - Shopping Norte", "Caixa 04 - Carla", "parcelado_sem_juros", "Ferramentas & Utilidades do Lar (2x)", 430.00, 430.00, 2, 215.00, "APROVADA", "2026-10-07 19:05"),
    ]

    cur.executemany("""
        INSERT INTO pos_transactions (
            nsu_code, holder_id, store_branch, cashier_name, modality,
            items_description, gross_amount, total_with_interest, installments,
            installment_amount, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, pos_txs)

    statements = [
        # 1. Renata (holder 3) - Vencida 2026-09-05 (39 dias atraso)
        (
            "FAT-2026/09-5518",
            3,
            "Setembro/2026",
            "Compras Matriz Centro (R$ 980,00) + Anuidade Faturada (R$ 14,90) + Seguro Conta Protegida (R$ 9,90) + SMS (R$ 5,90)",
            980.00,
            30.70,
            1010.70,
            "2026-08-26",
            "2026-09-05",
            "vencida",
            None,
            None,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br52040000530398654071010.705802BR",
            "23793.38128 60084.219018 25518.100009 8 9830000101070",
            "2026-10-08 14:20",
            "D+30",
            4
        ),
        # 2. Diego (holder 4) - Vencida 2026-09-25 (19 dias atraso)
        (
            "FAT-2026/09-3310",
            4,
            "Setembro/2026",
            "Compras Atacarejo Sul (R$ 640,00) + Anuidade Faturada (R$ 14,90) + Seguro Conta Protegida (R$ 9,90)",
            640.00,
            24.80,
            664.80,
            "2026-09-16",
            "2026-09-25",
            "vencida",
            None,
            None,
            "2026-10-16",
            "Diego confirmou no WhatsApp que vai pagar via PIX na sexta-feira (16/10) para liberar o cartão.",
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br5204000053039865406664.805802BR",
            "23793.38128 60084.219018 23310.100009 8 9850000066480",
            "2026-10-11 11:10",
            "D+15",
            3
        ),
        # 3. Juliana (holder 5) - Vencida 2026-10-10 (4 dias atraso)
        (
            "FAT-2026/10-8821",
            5,
            "Outubro/2026",
            "Compras Matriz Centro (R$ 520,00) + Anuidade Faturada (R$ 14,90) + Seguro Conta Protegida (R$ 9,90)",
            520.00,
            24.80,
            544.80,
            "2026-10-01",
            "2026-10-10",
            "vencida",
            None,
            None,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br5204000053039865406544.805802BR",
            "23793.38128 60084.219018 28821.100009 8 9865000054480",
            "2026-10-13 09:30",
            "D+3",
            1
        ),
        # 4. Patrícia (holder 6) - Vence Hoje 2026-10-14 (0 dias)
        (
            "FAT-2026/10-1094",
            6,
            "Outubro/2026",
            "Compras Hipermercado & Perfumaria (R$ 949,30) + Anuidade (R$ 14,90) + Seguro (R$ 9,90) + SMS (R$ 5,90)",
            949.30,
            30.70,
            980.00,
            "2026-10-05",
            "2026-10-14",
            "fechada",
            None,
            None,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br5204000053039865406980.005802BR",
            "23793.38128 60084.219018 21094.100009 8 9869000098000",
            "2026-10-14 08:30",
            "D0",
            1
        ),
        # 5. Marcos (holder 7) - Fatura Fechada vence 2026-10-20 (-6 dias)
        (
            "FAT-2026/10-6640",
            7,
            "Outubro/2026",
            "Compras Shopping Norte (R$ 430,00) + Anuidade Faturada (R$ 14,90) + Seguro Conta Protegida (R$ 9,90)",
            430.00,
            24.80,
            454.80,
            "2026-10-11",
            "2026-10-20",
            "fechada",
            None,
            None,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br5204000053039865406454.805802BR",
            "23793.38128 60084.219018 26640.100009 8 9875000045480",
            None,
            None,
            0
        ),
        # 6. Fatura Paga (Patrícia Setembro)
        (
            "FAT-2026/09-1094",
            6,
            "Setembro/2026",
            "Compras Hipermercado Setembro + Encargos Conta",
            815.20,
            24.80,
            840.00,
            "2026-09-05",
            "2026-09-14",
            "paga",
            "2026-09-14",
            840.00,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br",
            "23793.38128 60084.219018 21094.090009 8 9839000084000",
            "2026-09-14 09:00",
            "D0",
            1
        ),
        # 7. Fatura Recuperada no PIX c/ Desbloqueio (Juliana Setembro)
        (
            "FAT-2026/09-8821",
            5,
            "Setembro/2026",
            "Compras Matriz Centro + Seguro Conta Protegida",
            505.20,
            24.80,
            530.00,
            "2026-09-01",
            "2026-09-10",
            "paga",
            "2026-09-16",
            554.60,
            None,
            None,
            "00020126580014BR.GOV.BCB.PIX0126faturas@armarinhosfernando.com.br",
            "23793.38128 60084.219018 28821.090009 8 9835000053000",
            "2026-09-15 10:20",
            "D+5",
            2
        ),
    ]

    cur.executemany("""
        INSERT INTO card_statements (
            statement_code, holder_id, reference_month, items_summary,
            purchases_amount, fees_and_insurance_amount, original_amount,
            closing_date, due_date, status, paid_date, paid_amount,
            promise_date, promise_note, pix_key, digitable_line,
            last_contact_at, last_stage_sent, contact_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, statements)

    rules = [
        (
            -99,
            "ATIVACAO",
            "Boas-Vindas + Voucher 1ª Compra Imediata (Sem esperar plástico)",
            "WhatsApp Oficial",
            "amigavel",
            1,
            "🎉 {{cliente}}, seu {{nome_cartao}} foi aprovado! Voucher de 1ª Compra liberado!",
            "Olá, *{{cliente}}*! Parabéns! 🎉\n\nSeu *{{nome_cartao}}* (final {{final_cartao}}) foi *APROVADO* na *{{loja}}* com limite inicial de *{{limite_aprovado}}*!\n\n🛒 *Você já pode comprar agora mesmo sem esperar o cartão físico!* Basta apresentar seu Voucher Digital *{{voucher}}* e sua senha de 4 dígitos no caixa para ganhar *10% OFF na 1ª compra*!\n\n📱 Acesse seu Super App Prime Card: {{link_portal}}"
        ),
        (
            -9,
            "MELHOR-DIA",
            "Aviso de Melhor Dia de Compra (Fatura Fechou Hoje!)",
            "WhatsApp + Push App",
            "amigavel",
            1,
            "🛒 Hoje é o MELHOR DIA DE COMPRA do seu {{nome_cartao}}!",
            "Oi, *{{cliente}}*! Notícia boa da *{{loja}}*! 🛍️\n\nSua fatura fechou hoje! Isso significa que *qualquer compra feita a partir de hoje no seu {{nome_cartao}}* (final {{final_cartao}}) só será paga na fatura do *próximo mês* (até 40 dias para pagar)!\n\n• Seu Limite Disponível: *{{limite_disponivel}}*\n\nTe esperamos na loja!"
        ),
        (
            -5,
            "D-5",
            "Envio de Fatura Fechada (PDF / PIX / Boleto 5 dias antes)",
            "WhatsApp + SMS",
            "amigavel",
            1,
            "📄 Sua fatura {{nome_cartao}} de {{mes_ref}} fechou!",
            "Olá, *{{cliente}}*! 😊\n\nA fatura do seu *{{nome_cartao}}* (final {{final_cartao}}) de *{{mes_ref}}* já está disponível:\n\n• *Valor Total:* {{valor_original}}\n• *Pagamento Mínimo:* {{pagamento_minimo}}\n• *Vencimento:* {{vencimento}}\n\n⚡ *Pague com PIX e libere seu limite na mesma hora:*\n`{{chave_pix}}`\n\n📱 Ver fatura detalhada ou código de barras: {{link_portal}}"
        ),
        (
            0,
            "D0",
            "Alerta de Vencimento Hoje + PIX Libera Limite na Hora",
            "WhatsApp",
            "amigavel",
            1,
            "⏰ Sua fatura {{nome_cartao}} vence HOJE ({{vencimento}})",
            "Oi, *{{cliente}}*! Lembrete de que a fatura do seu *{{nome_cartao}}* no valor de *{{valor_original}}* vence *HOJE ({{vencimento}})*.\n\nEvite juros do rotativo e libere seu limite imediatamente para fazer compras na *{{loja}}* pagando via PIX:\n`{{chave_pix}}`\n\nAcesse seu App: {{link_portal}}"
        ),
        (
            3,
            "D+3",
            "Lembrete Pós-Vencimento (Evite o Bloqueio Temporário)",
            "WhatsApp",
            "amigavel",
            1,
            "⚠️ Fatura em aberto — Mantenha seu {{nome_cartao}} ativo!",
            "Olá, *{{cliente}}*, tudo bem?\n\nAinda não identificamos o pagamento da sua fatura *{{fatura}}* (vencida há {{dias_atraso}} dias).\n\nPara evitar o bloqueio preventivo do seu *{{nome_cartao}}* no caixa da *{{loja}}*, regularize hoje pelo valor atualizado de *{{valor_atualizado}}* (ou parcele sua fatura no App):\n\n👉 *Pagar ou Parcelar Fatura:* {{link_portal}}"
        ),
        (
            5,
            "D+5",
            "Bloqueio Preventivo no PDV + Desbloqueio Instantâneo via PIX",
            "WhatsApp + SMS",
            "firme",
            1,
            "🔒 Cartão temporariamente bloqueado — Pague c/ PIX e desbloqueie na hora!",
            "Olá, *{{cliente}}*.\n\nComo a fatura *{{fatura}}* completou *{{dias_atraso}} dias de atraso*, seu *{{nome_cartao}}* (final {{final_cartao}}) entrou em *bloqueio temporário para novas compras*.\n\n⚡ *Desbloqueio Imediato:* Pagando via PIX agora, nosso sistema *recompõe seu limite e desbloqueia seu cartão em segundos* no caixa da loja!\n\n• Valor Atualizado: *{{valor_atualizado}}*\n👉 *Quitar com Desconto ou Parcelar Fatura:* {{link_portal}}"
        ),
        (
            15,
            "D+15",
            "Campanha de Parcelamento de Fatura (Saia do Rotativo em até 6x)",
            "WhatsApp",
            "firme",
            1,
            "🤝 Parcele sua fatura {{nome_cartao}} em até 6x e reative seu cartão!",
            "Prezado(a) *{{cliente}}*,\n\nNão deixe os juros do rotativo acumularem! Liberamos no App do seu *{{nome_cartao}}* uma condição especial para você regularizar a fatura *{{fatura}}* ({{dias_atraso}} dias em atraso):\n\n✅ *Até 95% de desconto nos juros* para quitar à vista no PIX\n✅ Ou *Parcelamento de Fatura em até 6x fixas* (pagando a entrada no PIX seu cartão já é reabilitado)!\n\n👉 *Simular Acordo no App:* {{link_portal}}"
        ),
        (
            30,
            "D+30",
            "Notificação Pré-Negativação SCPC/Serasa & Quitação Especial",
            "WhatsApp + SMS",
            "extrajudicial",
            1,
            "🚨 AVISO SCPC/SERASA — CPF {{cpf}} ({{nome_cartao}})",
            "AVISO IMPORTANTE — *{{loja}} / {{nome_cartao}}*\nTitular: *{{cliente}}* (CPF: {{cpf}})\n\nA fatura *{{fatura}}* encontra-se vencida há *{{dias_atraso}} dias*, totalizando *{{valor_atualizado}}*.\n\nAntes do envio automático para registro no *Serasa / Boa Vista SCPC* em 48h, liberamos um *Desconto Especial de Quitação ou Parcelamento Direto* no App:\n\n🔗 *Regularizar Agora:* {{link_portal}}"
        ),
    ]

    cur.executemany("""
        INSERT INTO collection_rules (
            day_offset, stage_code, title, channel, tone, active,
            subject_template, message_template
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, rules)

    logs = [
        (
            None, 1, "Esteira Biometria + Serasa", "KYC-APROVADO",
            "Camila Ferreira dos Santos (CPF 384.912.048-22)",
            "Biometria Facial validada (99.4% FaceMatch) + CNH Digital conferida. Promotora Vanessa. Score: 685 pts. Limite: R$ 1.500,00.",
            "Pronto p/ Emitir Voucher",
            "2026-10-14 14:10"
        ),
        (
            None, 6, "Autorizador PDV (Caixa 02)", "VENDA-PDV",
            "Patrícia Nogueira Souza (Cartão Final 1094)",
            "Compra autorizada NSU-905882 no valor de R$ 949,30 (Modalidade: Rotativo Vista 40 dias). Senha validada.",
            "NSU-905882 Aprovada",
            "2026-10-02 14:50"
        ),
        (
            1, 3, "WhatsApp + SMS", "D+30",
            "Renata Cristina Almeida (5511991045520)",
            "Aviso pré-negativação D+30 enviado para FAT-2026/09-5518 (R$ 1.010,70). Cliente acessou o Super App Prime para simular parcelamento.",
            "Acessou App do Cartão",
            "2026-10-08 14:20"
        ),
        (
            2, 4, "WhatsApp Oficial", "D+15",
            "Diego Henrique Martins (5511977882310)",
            "Oferta de parcelamento de fatura D+15 enviada. Diego registrou promessa de pagamento via PIX para 16/10/2026.",
            "Promessa p/ 16/10",
            "2026-10-11 11:10"
        ),
    ]

    cur.executemany("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, logs)


def recommend_statement_stage(days_overdue, auto_block_days=5):
    if days_overdue <= -2:
        return "D-5"
    elif days_overdue in (-1, 0):
        return "D0"
    elif 1 <= days_overdue < auto_block_days:
        return "D+3"
    elif auto_block_days <= days_overdue <= 11:
        return "D+5"
    elif 12 <= days_overdue <= 24:
        return "D+15"
    else:
        return "D+30"


def enrich_statement(st_dict, store=None):
    if store is None:
        store = get_store_settings()
    days_overdue = calculate_days_overdue(st_dict["due_date"])
    calc = calculate_statement_amounts(
        st_dict["original_amount"],
        days_overdue,
        fine_pct=float(store.get("fine_pct", 2.0)),
        rotativo_monthly_pct=float(store.get("rotativo_interest_pct", 11.9)),
    )
    st_dict.update(calc)
    auto_block = int(store.get("auto_block_days", 5))
    st_dict["recommended_stage"] = recommend_statement_stage(days_overdue, auto_block)
    st_dict["card_blocked_by_delay"] = days_overdue >= auto_block and st_dict["status"] == "vencida"

    if st_dict["status"] == "paga":
        st_dict["bucket"] = "paid"
        st_dict["status_label"] = "Paga • Limite Liberado"
        st_dict["urgency_score"] = 0
    elif st_dict["status"] == "acordo":
        st_dict["bucket"] = "agreement"
        st_dict["status_label"] = "Fatura Parcelada"
        st_dict["urgency_score"] = 20
    else:
        if days_overdue < 0:
            st_dict["bucket"] = "preventive"
            st_dict["status_label"] = f"Fechada • Vence em {abs(days_overdue)}d"
            st_dict["urgency_score"] = 30
        elif days_overdue == 0:
            st_dict["bucket"] = "due_today"
            st_dict["status_label"] = "Vence Hoje (D0)"
            st_dict["urgency_score"] = 70
        elif days_overdue < auto_block:
            st_dict["bucket"] = "overdue_light"
            st_dict["status_label"] = f"Atraso Leve ({days_overdue}d)"
            st_dict["urgency_score"] = 78 + days_overdue
        elif days_overdue <= 25:
            st_dict["bucket"] = "overdue_blocked"
            st_dict["status_label"] = f"Cartão Bloqueado ({days_overdue}d)"
            st_dict["urgency_score"] = 88 + min(8, days_overdue // 3)
        else:
            st_dict["bucket"] = "overdue_critical"
            st_dict["status_label"] = f"Risco SCPC/Serasa ({days_overdue}d)"
            st_dict["urgency_score"] = 99

    return st_dict


def render_dm_template(template_str, holder_obj, st_obj=None, store=None):
    if store is None:
        store = get_store_settings()
    portal_id = st_obj["id"] if st_obj else 1
    link_portal = f"https://app.armarinhosfernando.com.br/portal?id={portal_id}"
    fmt_brl = lambda v: f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    replacements = {
        "{{loja}}": store["store_name"],
        "{{nome_cartao}}": store["card_brand_name"],
        "{{cliente}}": holder_obj["full_name"].split()[0] + " " + holder_obj["full_name"].split()[-1],
        "{{nome_completo}}": holder_obj["full_name"],
        "{{cpf}}": holder_obj["cpf"],
        "{{final_cartao}}": holder_obj.get("card_number_last4", "0000"),
        "{{voucher}}": holder_obj.get("voucher_code", "VCH-0000"),
        "{{limite_aprovado}}": fmt_brl(holder_obj.get("approved_limit", 1000)),
        "{{limite_disponivel}}": fmt_brl(max(0, (holder_obj.get("approved_limit", 0) - holder_obj.get("used_limit", 0)))),
        "{{fatura}}": st_obj["statement_code"] if st_obj else "FAT-ATUAL",
        "{{mes_ref}}": st_obj["reference_month"] if st_obj else "Outubro/2026",
        "{{vencimento}}": "/".join(reversed(st_obj["due_date"].split("-"))) if st_obj else f"{holder_obj.get('due_day', 10)}/10/2026",
        "{{dias_atraso}}": str(max(0, st_obj["days_overdue"])) if st_obj else "0",
        "{{valor_original}}": fmt_brl(st_obj["original_amount"]) if st_obj else "R$ 0,00",
        "{{pagamento_minimo}}": fmt_brl(st_obj["minimum_payment"]) if st_obj else "R$ 0,00",
        "{{multa_juros}}": fmt_brl(st_obj["total_charges"]) if st_obj else "R$ 0,00",
        "{{valor_atualizado}}": fmt_brl(st_obj["updated_amount"]) if st_obj else "R$ 0,00",
        "{{chave_pix}}": (st_obj.get("pix_key") if st_obj else None) or store["pix_key"],
        "{{link_portal}}": link_portal,
    }
    out = template_str
    for k, v in replacements.items():
        out = out.replace(k, str(v))
    return out


async def api_state(request):
    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    cur.execute("SELECT * FROM card_holders ORDER BY id ASC")
    holders = [dict(r) for r in cur.fetchall()]
    holders_map = {h["id"]: h for h in holders}

    cur.execute("SELECT * FROM card_statements ORDER BY due_date ASC")
    statements_raw = [dict(r) for r in cur.fetchall()]

    enriched_statements = []
    for st in statements_raw:
        h = holders_map.get(st["holder_id"], {})
        st["lead_id"] = st["holder_id"]
        st["client_name"] = h.get("full_name", "Titular")
        st["cpf"] = h.get("cpf", "")
        st["whatsapp"] = h.get("whatsapp", "")
        st["card_number_last4"] = h.get("card_number_last4", "0000")
        st["card_number_full"] = h.get("card_number_full", "6060 •••• •••• 0000")
        st["card_tier"] = h.get("card_tier", "Private Label Loja")
        st["approved_limit"] = h.get("approved_limit", 0.0)
        st["used_limit"] = h.get("used_limit", 0.0)
        st["credit_score"] = h.get("credit_score", 600)
        st["store_branch"] = h.get("store_branch", "Loja 01")
        st = enrich_statement(st, store)
        enriched_statements.append(st)

    for h in holders:
        h["available_limit"] = round(max(0.0, h["approved_limit"] - h["used_limit"]), 2)
        if h["credit_score"] >= 740:
            h["risk_tier"] = "A+"
        elif h["credit_score"] >= 560:
            h["risk_tier"] = "B"
        elif h["credit_score"] >= 450:
            h["risk_tier"] = "C"
        else:
            h["risk_tier"] = "D"

    cur.execute("""
        SELECT t.*, c.full_name as client_name, c.card_number_last4, c.cpf
        FROM pos_transactions t
        LEFT JOIN card_holders c ON t.holder_id = c.id
        ORDER BY t.id DESC LIMIT 30
    """)
    pos_transactions = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM collection_rules ORDER BY day_offset ASC")
    rules = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT l.*, s.statement_code, c.full_name as client_name, c.card_number_last4
        FROM interaction_logs l
        LEFT JOIN card_statements s ON l.statement_id = s.id
        LEFT JOIN card_holders c ON l.holder_id = c.id
        ORDER BY l.id DESC LIMIT 40
    """)
    logs = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT a.*, s.statement_code, c.full_name as client_name, c.cpf, c.card_number_last4
        FROM card_agreements a
        LEFT JOIN card_statements s ON a.statement_id = s.id
        LEFT JOIN card_holders c ON a.holder_id = c.id
        ORDER BY a.id DESC
    """)
    agreements = [dict(r) for r in cur.fetchall()]

    conn.close()

    # Calculate Prime Store & Promoter Metrics
    total_leads = len(holders)
    pending_leads = sum(1 for h in holders if h["lead_stage"] in ("novo_lead", "mesa_credito"))
    active_cards = sum(1 for h in holders if h["lead_stage"] in ("cartao_ativo", "aprovado_sem_compra"))
    blocked_cards = sum(1 for h in holders if h["lead_stage"] == "bloqueado_atraso")
    inactive_vouchers = sum(1 for h in holders if h["lead_stage"] == "aprovado_sem_compra" and h["first_purchase_done"] == 0)

    total_limit_granted = sum(h["approved_limit"] for h in holders if h["lead_stage"] not in ("novo_lead", "recusado"))
    total_limit_used = sum(h["used_limit"] for h in holders)

    # Ancillary revenue (Anuidade Faturada + Seguro Conta Protegida + SMS)
    seguros_ativos = sum(1 for h in holders if h.get("has_seguro_protegido") == 1)
    sms_ativos = sum(1 for h in holders if h.get("has_sms_alerta") == 1)
    monthly_ancillary_revenue = round(
        (active_cards * float(store.get("anuidade_faturada_brl", 14.90)))
        + (seguros_ativos * float(store.get("seguro_protegido_brl", 9.90)))
        + (sms_ativos * float(store.get("sms_alerta_brl", 5.90))),
        2
    )

    total_open_updated = 0.0
    total_overdue_updated = 0.0
    total_charges_accrued = 0.0
    total_recovered = 0.0
    overdue_count = 0

    aging = {
        "preventive": {"label": "Faturas Fechadas (A Vencer)", "amount": 0.0, "count": 0},
        "due_today": {"label": "Vence Hoje (D0)", "amount": 0.0, "count": 0},
        "overdue_light": {"label": "Atraso Leve (1 a 4 dias)", "amount": 0.0, "count": 0},
        "overdue_blocked": {"label": "Cartão Bloqueado no PDV (5 a 25d)", "amount": 0.0, "count": 0},
        "overdue_critical": {"label": "Pré-Negativação SCPC/Serasa (+25d)", "amount": 0.0, "count": 0},
    }

    for st in enriched_statements:
        if st["status"] == "paga":
            total_recovered += st["paid_amount"] or st["original_amount"]
        else:
            total_open_updated += st["updated_amount"]
            if st["days_overdue"] > 0:
                total_overdue_updated += st["updated_amount"]
                total_charges_accrued += st["total_charges"]
                overdue_count += 1
            b = st["bucket"]
            if b in aging:
                aging[b]["amount"] = round(aging[b]["amount"] + st["updated_amount"], 2)
                aging[b]["count"] += 1

    # Promoter ranking
    promoter_stats = {}
    for h in holders:
        p = h["promoter_name"]
        if p not in promoter_stats:
            promoter_stats[p] = {
                "promoter_name": p,
                "store_branch": h["store_branch"],
                "cards_captured": 0,
                "activated_first_purchase": 0,
                "seguros_sold": 0,
                "commission_brl": 0.0,
            }
        promoter_stats[p]["cards_captured"] += 1
        if h["first_purchase_done"] == 1:
            promoter_stats[p]["activated_first_purchase"] += 1
            promoter_stats[p]["commission_brl"] += float(store.get("comissao_promotor_brl", 6.0))
        if h.get("has_seguro_protegido") == 1:
            promoter_stats[p]["seguros_sold"] += 1
            promoter_stats[p]["commission_brl"] += float(store.get("comissao_seguro_brl", 3.5))

    promoters_ranking = sorted(promoter_stats.values(), key=lambda x: x["commission_brl"], reverse=True)

    priority_queue = sorted(
        [s for s in enriched_statements if s["status"] not in ("paga", "acordo")],
        key=lambda x: (x["urgency_score"], x["updated_amount"]),
        reverse=True
    )

    filter_holder_id = request.query.get("holder_id")
    admin_users = []
    if filter_holder_id and filter_holder_id.isdigit():
        hid = int(filter_holder_id)
        holders = [h for h in holders if h["id"] == hid]
        pos_transactions = [t for t in pos_transactions if t["holder_id"] == hid]
        enriched_statements = [s for s in enriched_statements if s["holder_id"] == hid]
    else:
        cur = get_db().cursor()
        cur.execute("SELECT * FROM admin_users ORDER BY id ASC")
        admin_users = [dict(r) for r in cur.fetchall()]
        cur.connection.close()

    return web.json_response({
        "today": TODAY_STR,
        "store": store,
        "admin_users": admin_users,
        "kpis": {
            "total_leads": total_leads,
            "pending_leads": pending_leads,
            "active_cards": active_cards,
            "blocked_cards": blocked_cards,
            "inactive_vouchers": inactive_vouchers,
            "total_limit_granted": round(total_limit_granted, 2),
            "total_limit_used": round(total_limit_used, 2),
            "monthly_ancillary_revenue": monthly_ancillary_revenue,
            "seguros_ativos": seguros_ativos,
            "total_open_updated": round(total_open_updated, 2),
            "total_overdue_updated": round(total_overdue_updated, 2),
            "total_charges_accrued": round(total_charges_accrued, 2),
            "total_recovered": round(total_recovered, 2),
            "overdue_count": overdue_count,
            "approval_rate_pct": 88.0,
        },
        "aging": aging,
        "priority_queue": priority_queue,
        "leads": holders,
        "pos_transactions": pos_transactions,
        "promoters_ranking": promoters_ranking,
        "statements": enriched_statements,
        "rules": rules,
        "logs": logs,
        "agreements": agreements,
    })


async def api_create_lead(request):
    """Prime Card Proposal with Biometria, RG/CNH, Endereço, Renda, Seguro Conta Protegida, SMS Alert and Esteira de Crédito."""
    data = await request.json()
    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    full_name = (data.get("full_name") or "Novo Cliente da Loja").strip()
    cpf = (data.get("cpf") or "390.112.840-10").strip()
    rg_cnh = (data.get("rg_cnh") or "42.901.882-X SSP/SP").strip()
    birth_date = data.get("birth_date") or "1993-05-15"
    mother_name = (data.get("mother_name") or "Maria Aparecida Silva").strip()
    whatsapp = (data.get("whatsapp") or "5511999998888").strip()
    email = (data.get("email") or "cliente@email.com").strip()
    occupation = (data.get("occupation") or "Autônomo / Comerciante").strip()
    declared_income = float(data.get("declared_income") or 3200.0)
    store_branch = data.get("store_branch") or "Matriz 25 de Março"
    promoter_name = data.get("promoter_name") or data.get("seller_name") or "Vanessa (Consultora Prime)"
    due_day = int(data.get("due_day") or 10)
    best_day = compute_best_purchase_day(due_day)
    credit_score = int(data.get("credit_score") or 680)
    has_seguro = 1 if data.get("has_seguro_protegido", True) else 0
    has_sms = 1 if data.get("has_sms_alerta", True) else 0
    biometria_status = data.get("biometria_status") or "Validada (99.4% FaceMatch)"
    doc_status = data.get("doc_status") or "CNH/RG Validado"
    address_summary = (data.get("address_summary") or "").strip()
    company_name = (data.get("company_name") or "").strip()
    routing_mode = data.get("routing_mode") or "auto"

    _, tier = suggest_credit_limit(declared_income, credit_score)
    # Sem limite pré-aprovado ou aprovação automática no cadastro: toda proposta vai para análise na Mesa de Crédito
    lead_stage = "mesa_credito"
    suggested_limit = 0.0

    last4 = str(random.randint(1000, 9999))
    mid4 = str(random.randint(1000, 9999))
    card_full = f"6060 8421 {mid4} {last4}"
    cvv = str(random.randint(100, 999))
    pin = str(data.get("card_pin") or last4).strip()
    voucher = f"VCH-{last4}-AF"
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    extra_notes = f"Proposta captada em {store_branch} por {promoter_name}."
    if address_summary:
        extra_notes += f" End: {address_summary}."
    if company_name:
        extra_notes += f" Emp: {company_name}."
    extra_notes += f" Link WhatsApp de Configuração (Vencimento e Senha) enviado para {whatsapp}."

    cur.execute("""
        INSERT INTO card_holders (
            full_name, cpf, rg_cnh, birth_date, mother_name, whatsapp, email,
            occupation, declared_income, store_branch, promoter_name, credit_score,
            biometria_status, doc_status, otp_verified, lead_stage,
            approved_limit, used_limit, card_number_full, card_number_last4,
            card_cvv, card_expiry, card_pin, card_tier, due_day, best_purchase_day,
            has_seguro_protegido, has_sms_alerta, first_purchase_done, voucher_code,
            notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0.0, ?, ?, ?, '10/2031', ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
    """, (
        full_name, cpf, rg_cnh, birth_date, mother_name, whatsapp, email,
        occupation, declared_income, store_branch, promoter_name, credit_score,
        biometria_status, doc_status,
        lead_stage, suggested_limit, card_full, last4, cvv, pin, tier, due_day, best_day,
        has_seguro, has_sms, voucher,
        extra_notes,
        now_str
    ))
    new_id = cur.lastrowid

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'WhatsApp Oficial', 'CONFIG-CARTAO', ?, ?, ?, ?)
    """, (
        new_id,
        f"{full_name} ({whatsapp})",
        f"Olá {full_name}! Recebemos seu cadastro do Cartão Armarinhos Fernando. Acesse o link exclusivo para escolher o seu Melhor Dia de Vencimento e cadastrar a sua Senha pessoal.",
        "Link de Configuração Enviado no WhatsApp",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({
        "ok": True,
        "id": new_id,
        "lead_id": new_id,
        "full_name": full_name,
        "cpf": cpf,
        "whatsapp": whatsapp,
        "lead_stage": lead_stage,
        "stage": lead_stage,
        "approved_limit": suggested_limit,
        "card_tier": tier,
        "card_number_full": card_full,
        "card_number_last4": last4,
        "card_cvv": cvv,
        "card_expiry": "10/2031",
        "card_pin": pin,
        "due_day": due_day,
        "best_purchase_day": best_day,
        "credit_score": credit_score,
        "biometria_status": biometria_status,
        "voucher_code": voucher,
        "whatsapp_config_sent": True
    })


async def api_lookup_cep(request):
    """Real-time Brazilian CEP lookup via ViaCEP / BrasilAPI / OpenCEP."""
    import urllib.request
    import asyncio

    raw_cep = (request.query.get("cep") or "").strip()
    cep = "".join(c for c in raw_cep if c.isdigit())
    if len(cep) != 8:
        return web.json_response({"ok": False, "error": "CEP deve conter 8 dígitos."}, status=400)

    def _fetch_cep_sync(c):
        logradouro = bairro = localidade = uf = ""
        # 1. ViaCEP
        try:
            req = urllib.request.Request(
                f"https://viacep.com.br/ws/{c}/json/",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                d = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if not d.get("erro"):
                    logradouro = (d.get("logradouro") or "").strip()
                    bairro = (d.get("bairro") or "").strip()
                    localidade = (d.get("localidade") or "").strip()
                    uf = (d.get("uf") or "").strip()
        except Exception:
            pass

        # 2. BrasilAPI fallback
        if not localidade:
            try:
                req2 = urllib.request.Request(
                    f"https://brasilapi.com.br/api/cep/v1/{c}",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req2, timeout=4.5) as resp2:
                    d2 = json.loads(resp2.read().decode("utf-8", errors="ignore"))
                    logradouro = (d2.get("street") or logradouro).strip()
                    bairro = (d2.get("neighborhood") or bairro).strip()
                    localidade = (d2.get("city") or localidade).strip()
                    uf = (d2.get("state") or uf).strip()
            except Exception:
                pass

        # 3. OpenCEP fallback
        if not localidade:
            try:
                req3 = urllib.request.Request(
                    f"https://opencep.com/v1/{c}.json",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req3, timeout=4.5) as resp3:
                    d3 = json.loads(resp3.read().decode("utf-8", errors="ignore"))
                    logradouro = (d3.get("logradouro") or logradouro).strip()
                    bairro = (d3.get("bairro") or bairro).strip()
                    localidade = (d3.get("localidade") or localidade).strip()
                    uf = (d3.get("uf") or uf).strip()
            except Exception:
                pass

        return logradouro, bairro, localidade, uf

    logradouro, bairro, localidade, uf = await asyncio.to_thread(_fetch_cep_sync, cep)
    if not localidade and not logradouro:
        return web.json_response({"ok": False, "error": "CEP não encontrado na base dos Correios."}, status=404)

    formatted_cep = f"{cep[:5]}-{cep[5:]}"
    parts = [p for p in [logradouro, bairro] if p]
    city_uf = f"{localidade}/{uf}".strip("/")
    full_street = f"{' - '.join(parts)}, {city_uf}" if parts else city_uf

    return web.json_response({
        "ok": True,
        "cep": formatted_cep,
        "logradouro": logradouro,
        "bairro": bairro,
        "localidade": localidade,
        "uf": uf,
        "full_street": full_street
    })


async def api_send_whatsapp_card_config(request):
    """Dispatches the card configuration link (Melhor Dia de Vencimento & Senha) directly to the customer's registered WhatsApp."""
    data = await request.json()
    whatsapp = "".join(c for c in (data.get("whatsapp") or "") if c.isdigit())
    full_name = (data.get("full_name") or "Cliente").strip()
    cpf = (data.get("cpf") or "").strip()
    if not whatsapp or len(whatsapp) < 10:
        return web.json_response({"ok": False, "error": "Informe o WhatsApp do cliente no Passo 1."}, status=400)
    if not whatsapp.startswith("55") and len(whatsapp) in (10, 11):
        whatsapp = "55" + whatsapp

    config_url = f"https://apparmarinhosfernando.com/configurar?cpf={cpf}"
    msg_text = (
        f"Olá, *{full_name}*! 💳✨\n"
        f"Recebemos sua solicitação do *Cartão Armarinhos Fernando*.\n\n"
        f"Acesse o link seguro abaixo para cadastrar o seu *Melhor Dia de Vencimento* e definir a sua *Senha Pessoal* do Cartão e Aplicativo:\n"
        f"👉 {config_url}"
    )

    conn = get_db()
    cur = conn.cursor()
    holder_id = 1
    if cpf:
        cur.execute("SELECT id FROM card_holders WHERE cpf = ? ORDER BY id DESC LIMIT 1", (cpf,))
        row = cur.fetchone()
        if row:
            holder_id = row["id"]
    now_str = "2026-10-16 " + datetime.datetime.now().strftime("%H:%M")
    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'WhatsApp Oficial', 'CONFIG-CARTAO', ?, ?, ?, ?)
    """, (
        holder_id,
        f"{full_name} ({whatsapp})",
        msg_text,
        "Link de Vencimento e Senha enviado via WhatsApp",
        now_str
    ))
    conn.commit()
    conn.close()

    return web.json_response({
        "ok": True,
        "whatsapp": whatsapp,
        "config_url": config_url,
        "message": msg_text
    })


async def api_update_lead_stage(request):
    data = await request.json()
    lead_id = int(data.get("lead_id"))
    new_stage = data.get("lead_stage") or data.get("stage") or "aprovado_sem_compra"
    approved_limit = data.get("approved_limit")

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (lead_id,))
    holder = cur.fetchone()
    if not holder:
        conn.close()
        return web.json_response({"error": "Portador não encontrado"}, status=404)

    final_limit = float(approved_limit) if approved_limit is not None else float(holder["approved_limit"])
    if new_stage in ("aprovado_sem_compra", "cartao_ativo") and final_limit <= 0:
        final_limit, _ = suggest_credit_limit(float(holder["declared_income"] or 2500), int(holder["credit_score"] or 680))
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        UPDATE card_holders
        SET lead_stage = ?, approved_limit = ?
        WHERE id = ?
    """, (new_stage, final_limit, lead_id))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'Mesa de Crédito Prime', 'DECISAO-MESA', ?, ?, ?, ?)
    """, (
        lead_id,
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Cartão atualizado para {new_stage.upper()} com limite de R$ {final_limit:,.2f}. Voucher: {holder['voucher_code']}.",
        f"Status: {new_stage}",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def api_update_holder(request):
    """Full update of any Cardholder field: Limit, PIN, Due Day (Best Purchase Day), Seguro Conta Protegida, SMS Alerta, Stage, or Personal Info."""
    data = await request.json()
    lead_id = int(data.get("lead_id") or data.get("id"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return web.json_response({"ok": False, "error": "Portador não encontrado"}, status=404)

    holder = dict(row)
    full_name = (data.get("full_name") if data.get("full_name") is not None else holder["full_name"]).strip()
    cpf = (data.get("cpf") if data.get("cpf") is not None else holder["cpf"]).strip()
    rg_cnh = (data.get("rg_cnh") if data.get("rg_cnh") is not None else holder["rg_cnh"]).strip()
    whatsapp = (data.get("whatsapp") if data.get("whatsapp") is not None else holder["whatsapp"]).strip()
    store_branch = data.get("store_branch") if data.get("store_branch") is not None else holder["store_branch"]
    promoter_name = data.get("promoter_name") if data.get("promoter_name") is not None else holder["promoter_name"]
    credit_score = int(data.get("credit_score") if data.get("credit_score") is not None else holder["credit_score"])
    approved_limit = float(data.get("approved_limit") if data.get("approved_limit") is not None else holder["approved_limit"])
    due_day = int(data.get("due_day") if data.get("due_day") is not None else holder["due_day"])
    best_purchase_day = compute_best_purchase_day(due_day)
    card_pin = str(data.get("card_pin") if data.get("card_pin") is not None else holder["card_pin"])[:4]
    lead_stage = data.get("lead_stage") if data.get("lead_stage") is not None else holder["lead_stage"]
    has_seguro = int(1 if data["has_seguro_protegido"] else 0) if "has_seguro_protegido" in data else int(holder["has_seguro_protegido"])
    has_sms = int(1 if data["has_sms_alerta"] else 0) if "has_sms_alerta" in data else int(holder["has_sms_alerta"])

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        UPDATE card_holders
        SET full_name = ?, cpf = ?, rg_cnh = ?, whatsapp = ?,
            store_branch = ?, promoter_name = ?, credit_score = ?,
            approved_limit = ?, due_day = ?, best_purchase_day = ?,
            card_pin = ?, lead_stage = ?, has_seguro_protegido = ?, has_sms_alerta = ?
        WHERE id = ?
    """, (
        full_name, cpf, rg_cnh, whatsapp,
        store_branch, promoter_name, credit_score,
        approved_limit, due_day, best_purchase_day,
        card_pin, lead_stage, has_seguro, has_sms,
        lead_id
    ))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'Cadastro / Super App Prime', 'ATUALIZACAO-PORTADOR', ?, ?, ?, ?)
    """, (
        lead_id,
        f"{full_name} (Final {holder['card_number_last4']})",
        f"Cadastro atualizado: Limite R$ {approved_limit:,.2f} | Venc. Dia {due_day} (Melhor Dia {best_purchase_day}) | PIN: {card_pin} | Seguro: {'Sim' if has_seguro else 'Não'} | SMS: {'Sim' if has_sms else 'Não'}.",
        f"Atualizado ({lead_stage})",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({
        "ok": True,
        "id": lead_id,
        "approved_limit": approved_limit,
        "due_day": due_day,
        "best_purchase_day": best_purchase_day,
        "card_pin": card_pin,
        "lead_stage": lead_stage,
        "has_seguro_protegido": has_seguro,
        "has_sms_alerta": has_sms
    })


async def api_pos_purchase(request):
    """Prime WebPOS Authorizer: Validates Card/Voucher, 4-digit PIN, Available Limit, Modality, and generates NSU + Thermal Receipt + Statement."""
    data = await request.json()
    lead_id = int(data.get("lead_id"))
    modality = data.get("modality") or "parcelado_sem_juros"
    items_summary = (data.get("items_summary") or "Compras Supermercado & Bazar").strip()
    amount = float(data.get("amount") or 380.0)
    installments = int(data.get("installments") or 1)
    due_date = data.get("due_date") or "2026-11-10"
    cashier_name = data.get("cashier_name") or "Caixa 01 - Frente de Loja"
    pin_code = (data.get("pin_code") or "").strip()
    terminal_id = data.get("terminal_id") or "WEBPOS-TERM-01"

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return web.json_response({"ok": False, "error": "Portador não encontrado"}, status=404)

    holder = dict(row)

    # Check if card is blocked due to overdue statement
    if holder["lead_stage"] == "bloqueado_atraso" and not data.get("force_supervisor"):
        conn.close()
        return web.json_response({
            "ok": False,
            "code": "CARTAO_BLOQUEADO_ATRASO",
            "error": f"TRANSAÇÃO NEGADA NO WEBPOS (CÓD 57): Cartão Final {holder['card_number_last4']} bloqueado por atraso superior a {store.get('auto_block_days', 5)} dias. Receba a fatura no caixa (F4) para desbloquear na hora!"
        }, status=400)

    # Validate 4-digit PIN if provided
    if pin_code and pin_code != str(holder.get("card_pin", "")):
        conn.close()
        return web.json_response({
            "ok": False,
            "code": "SENHA_INVALIDA",
            "error": f"TRANSAÇÃO NEGADA NO WEBPOS (CÓD 55): Senha PIN incorreta para o Cartão Final {holder['card_number_last4']}."
        }, status=400)

    available = max(0.0, holder["approved_limit"] - holder["used_limit"])
    if amount > available and holder["approved_limit"] > 0:
        conn.close()
        return web.json_response({
            "ok": False,
            "code": "SALDO_INSUFICIENTE",
            "error": f"TRANSAÇÃO NEGADA NO WEBPOS (CÓD 51): Valor (R$ {amount:,.2f}) excede o Limite Disponível (R$ {available:,.2f}). Solicite Aumento Express no WebPOS (F6)!"
        }, status=400)

    # Apply 10% OFF if first purchase
    discount_applied = False
    net_amount = amount
    if holder["first_purchase_done"] == 0 and data.get("apply_first_discount", True):
        disc_pct = float(store.get("first_purchase_discount_pct", 10.0))
        net_amount = round(amount * (1.0 - disc_pct / 100.0), 2)
        discount_applied = True

    # Apply interest if modality is crediario_com_juros or saque_facil
    total_with_interest = net_amount
    interest_rate_used = 0.0
    if modality in ("crediario_com_juros", "saque_facil") and installments >= 1:
        interest_rate_used = float(store.get("crediario_interest_pct", 4.99))
        rate = interest_rate_used / 100.0
        total_with_interest = round(net_amount * ((1.0 + rate) ** installments), 2)

    installment_val = round(total_with_interest / max(1, installments), 2)
    nsu_code = f"NSU-{random.randint(100000, 999999)}"
    auth_code = f"AUTH-{random.randint(1000, 9999)}PR"
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        INSERT INTO pos_transactions (
            nsu_code, holder_id, store_branch, cashier_name, modality,
            items_description, gross_amount, total_with_interest, installments,
            installment_amount, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APROVADA', ?)
    """, (
        nsu_code, lead_id, holder["store_branch"], cashier_name, modality,
        items_summary, amount, total_with_interest, installments,
        installment_val, now_str
    ))
    tx_id = cur.lastrowid

    # Calculate monthly fees on statement (Anuidade Faturada + Seguro + SMS)
    fees = float(store.get("anuidade_faturada_brl", 14.90))
    if holder.get("has_seguro_protegido") == 1:
        fees += float(store.get("seguro_protegido_brl", 9.90))
    if holder.get("has_sms_alerta") == 1:
        fees += float(store.get("sms_alerta_brl", 5.90))
    fees = round(fees, 2)

    statement_total = round(installment_val + fees, 2)
    st_code = f"FAT-2026/{holder['card_number_last4']}-{datetime.datetime.now().strftime('%M%S')}"
    days_overdue = calculate_days_overdue(due_date)
    st_status = "vencida" if days_overdue > 0 else "fechada"
    new_used_limit = round(holder["used_limit"] + total_with_interest, 2)
    new_available_limit = round(max(0.0, holder["approved_limit"] - new_used_limit), 2)
    new_stage = "bloqueado_atraso" if days_overdue >= int(store.get("auto_block_days", 5)) else "cartao_ativo"

    cur.execute("""
        UPDATE card_holders
        SET used_limit = ?, first_purchase_done = 1, lead_stage = ?
        WHERE id = ?
    """, (new_used_limit, new_stage, lead_id))

    desc = (
        f"[{nsu_code}] {items_summary} ({installments}x de R$ {installment_val:,.2f})"
        + (" [10% OFF 1ª Compra!]" if discount_applied else "")
        + f" + Anuidade/Seguro (R$ {fees:,.2f})"
    )
    pix_key = f"00020126580014BR.GOV.BCB.PIX0126{store['pix_key']}5204000053039865406{statement_total:.2f}5802BR"
    digitable_line = f"23793.38128 60084.219018 2{holder['card_number_last4']}.100009 8 9890{int(statement_total * 100):010d}"

    cur.execute("""
        INSERT INTO card_statements (
            statement_code, holder_id, reference_month, items_summary,
            purchases_amount, fees_and_insurance_amount, original_amount,
            closing_date, due_date, status, pix_key, digitable_line
        ) VALUES (?, ?, 'Outubro/2026', ?, ?, ?, ?, '2026-10-10', ?, ?, ?, ?)
    """, (st_code, lead_id, desc, installment_val, fees, statement_total, due_date, st_status, pix_key, digitable_line))
    st_id = cur.lastrowid

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'Terminal WebPOS Caixa', 'VENDA-APROVADA', ?, ?, ?, ?)
    """, (
        st_id,
        lead_id,
        f"{holder['full_name']} (Cartão {holder['card_number_last4']})",
        f"Venda {nsu_code} ({auth_code}) APROVADA no WebPOS ({modality}): {desc}. Fatura: R$ {statement_total:,.2f}.",
        f"Aprovada ({nsu_code})",
        now_str
    ))

    conn.commit()
    conn.close()

    receipt = {
        "type": "VENDA_CARTAO",
        "title": "COMPROVANTE DE VENDA WEBPOS PRIME",
        "nsu_code": nsu_code,
        "auth_code": auth_code,
        "terminal_id": terminal_id,
        "store_name": store["store_name"],
        "store_cnpj": store["cnpj"],
        "card_brand": store["card_brand_name"],
        "store_branch": holder["store_branch"],
        "cashier_name": cashier_name,
        "client_name": holder["full_name"],
        "cpf": holder["cpf"],
        "card_masked": f"6060 8421 **** {holder['card_number_last4']}",
        "voucher_code": holder["voucher_code"],
        "modality": modality,
        "items_summary": items_summary,
        "gross_amount": amount,
        "net_amount": net_amount,
        "discount_applied": discount_applied,
        "interest_rate_pct": interest_rate_used,
        "total_with_interest": total_with_interest,
        "installments": installments,
        "installment_val": installment_val,
        "due_date": due_date,
        "new_available_limit": new_available_limit,
        "approved_limit": holder["approved_limit"],
        "created_at": now_str,
    }

    return web.json_response({
        "ok": True,
        "tx_id": tx_id,
        "nsu_code": nsu_code,
        "auth_code": auth_code,
        "statement_id": st_id,
        "discount_applied": discount_applied,
        "installment_val": installment_val,
        "fees": fees,
        "statement_total": statement_total,
        "new_available_limit": new_available_limit,
        "receipt": receipt
    })


async def api_pos_reverse(request):
    """Prime WebPOS Supervisor Transaction Reversal (Estorno / Cancelamento de NSU no Caixa)."""
    data = await request.json()
    tx_id = data.get("tx_id")
    nsu_code = (data.get("nsu_code") or "").strip().upper()
    reason = (data.get("reason") or "Cancelamento solicitado no caixa / desistência").strip()
    supervisor_name = (data.get("supervisor_name") or "Supervisor Fiscal Loja").strip()

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    if tx_id:
        cur.execute("SELECT * FROM pos_transactions WHERE id = ?", (int(tx_id),))
    else:
        cur.execute("SELECT * FROM pos_transactions WHERE UPPER(nsu_code) = ?", (nsu_code,))
    tx_row = cur.fetchone()

    if not tx_row:
        conn.close()
        return web.json_response({"ok": False, "error": f"Transação NSU {nsu_code or tx_id} não localizada no WebPOS."}, status=404)

    tx = dict(tx_row)
    if tx["status"] == "ESTORNADA":
        conn.close()
        return web.json_response({"ok": False, "error": f"A transação {tx['nsu_code']} já foi estornada anteriormente."}, status=400)

    cur.execute("SELECT * FROM card_holders WHERE id = ?", (tx["holder_id"],))
    holder = dict(cur.fetchone())

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")
    restored_used = max(0.0, round(holder["used_limit"] - float(tx["total_with_interest"]), 2))
    new_available_limit = round(max(0.0, holder["approved_limit"] - restored_used), 2)

    cur.execute("UPDATE pos_transactions SET status = 'ESTORNADA' WHERE id = ?", (tx["id"],))
    cur.execute("UPDATE card_holders SET used_limit = ? WHERE id = ?", (restored_used, holder["id"]))

    # Also cancel matching statement if created from this NSU
    cur.execute("SELECT * FROM card_statements WHERE holder_id = ? AND items_summary LIKE ? ORDER BY id DESC LIMIT 1", (holder["id"], f"%{tx['nsu_code']}%"))
    st_match = cur.fetchone()
    if st_match:
        cur.execute("UPDATE card_statements SET status = 'paga', paid_date = ?, paid_amount = 0.0, promise_note = ? WHERE id = ?", (TODAY_STR, f"Estornada no WebPOS ({tx['nsu_code']}): {reason}", st_match["id"]))

    estorno_code = f"EST-{random.randint(100000, 999999)}"
    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'WebPOS Supervisor', 'ESTORNO-NSU', ?, ?, ?, ?)
    """, (
        holder["id"],
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Estorno {estorno_code} referente ao {tx['nsu_code']} (R$ {tx['total_with_interest']:,.2f}) autorizado por {supervisor_name}. Motivo: {reason}. Limite devolvido!",
        f"Estornado ({tx['nsu_code']})",
        now_str
    ))

    conn.commit()
    conn.close()

    receipt = {
        "type": "ESTORNO_VENDA",
        "title": "COMPROVANTE DE ESTORNO / CANCELAMENTO WEBPOS",
        "nsu_code": tx["nsu_code"],
        "auth_code": estorno_code,
        "terminal_id": "WEBPOS-SUPERVISOR",
        "store_name": store["store_name"],
        "store_cnpj": store["cnpj"],
        "card_brand": store["card_brand_name"],
        "store_branch": tx["store_branch"],
        "cashier_name": supervisor_name,
        "client_name": holder["full_name"],
        "cpf": holder["cpf"],
        "card_masked": f"6060 8421 **** {holder['card_number_last4']}",
        "modality": tx["modality"],
        "items_summary": f"ESTORNO: {tx['items_description']} ({reason})",
        "gross_amount": tx["gross_amount"],
        "total_with_interest": tx["total_with_interest"],
        "installments": tx["installments"],
        "installment_val": tx["installment_amount"],
        "new_available_limit": new_available_limit,
        "approved_limit": holder["approved_limit"],
        "created_at": now_str,
    }

    return web.json_response({
        "ok": True,
        "estorno_code": estorno_code,
        "nsu_code": tx["nsu_code"],
        "restored_amount": tx["total_with_interest"],
        "new_available_limit": new_available_limit,
        "receipt": receipt
    })


async def api_pos_pay_invoice(request):
    """Prime WebPOS Cashier Invoice Payment: Customer pays statement at store cashier (Cash, PIX PDV, Debit) and unlocks card limit immediately."""
    data = await request.json()
    statement_id = int(data.get("statement_id"))
    payment_method = data.get("payment_method") or "Dinheiro no Caixa (Espécie)"
    payment_type = data.get("payment_type") or "total"  # 'total' or 'minimo'
    cashier_name = data.get("cashier_name") or "Caixa 01 - Frente de Loja"
    paid_amount_input = data.get("paid_amount")

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    cur.execute("SELECT * FROM card_statements WHERE id = ?", (statement_id,))
    st_row = cur.fetchone()
    if not st_row:
        conn.close()
        return web.json_response({"ok": False, "error": "Fatura não localizada."}, status=404)

    st = enrich_statement(dict(st_row), store)
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = dict(cur.fetchone())

    if paid_amount_input is not None:
        final_paid = float(paid_amount_input)
    elif payment_type == "minimo":
        final_paid = float(st["minimum_payment"])
    else:
        final_paid = float(st["updated_amount"])

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")
    rec_nsu = f"REC-{random.randint(100000, 999999)}"

    cur.execute("""
        UPDATE card_statements
        SET status = 'paga', paid_date = ?, paid_amount = ?
        WHERE id = ?
    """, (TODAY_STR, final_paid, statement_id))

    # Restore credit limit and unblock card immediately
    limit_restored = st["original_amount"] if payment_type == "total" else round(final_paid * 0.85, 2)
    restored_used = max(0.0, round(holder["used_limit"] - limit_restored, 2))
    new_available_limit = round(max(0.0, holder["approved_limit"] - restored_used), 2)
    new_score = min(995, holder["credit_score"] + 25)

    cur.execute("""
        UPDATE card_holders
        SET used_limit = ?, lead_stage = 'cartao_ativo', credit_score = ?
        WHERE id = ?
    """, (restored_used, new_score, holder["id"]))

    cur.execute("""
        INSERT INTO pos_transactions (
            nsu_code, holder_id, store_branch, cashier_name, modality,
            items_description, gross_amount, total_with_interest, installments,
            installment_amount, status, created_at
        ) VALUES (?, ?, ?, ?, 'recebimento_fatura', ?, ?, ?, 1, ?, 'RECEBIDA CAIXA', ?)
    """, (
        rec_nsu, holder["id"], holder["store_branch"], cashier_name,
        f"Recebimento Fatura {st['statement_code']} ({payment_method})",
        final_paid, final_paid, final_paid, now_str
    ))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'WebPOS Gaveta Caixa', 'RECEBIMENTO-CAIXA', ?, ?, ?, ?)
    """, (
        statement_id, holder["id"],
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Fatura {st['statement_code']} paga no WebPOS da loja ({payment_method} - R$ {final_paid:,.2f} - {rec_nsu}). Limite liberado na hora: R$ {new_available_limit:,.2f}!",
        f"Recebida Caixa ({rec_nsu})",
        now_str
    ))

    conn.commit()
    conn.close()

    receipt = {
        "type": "RECEBIMENTO_FATURA",
        "title": "COMPROVANTE DE PAGAMENTO DE FATURA WEBPOS",
        "nsu_code": rec_nsu,
        "auth_code": f"LIQ-{statement_id:04d}PR",
        "terminal_id": "WEBPOS-CAIXA-01",
        "store_name": store["store_name"],
        "store_cnpj": store["cnpj"],
        "card_brand": store["card_brand_name"],
        "store_branch": holder["store_branch"],
        "cashier_name": cashier_name,
        "client_name": holder["full_name"],
        "cpf": holder["cpf"],
        "card_masked": f"6060 8421 **** {holder['card_number_last4']}",
        "modality": f"PAGAMENTO FATURA ({payment_method})",
        "items_summary": f"Baixa Fatura {st['statement_code']} ({'Quitação Total' if payment_type == 'total' else 'Pagamento Mínimo 15%'})",
        "gross_amount": st["updated_amount"],
        "total_with_interest": final_paid,
        "installments": 1,
        "installment_val": final_paid,
        "new_available_limit": new_available_limit,
        "approved_limit": holder["approved_limit"],
        "created_at": now_str,
    }

    return web.json_response({
        "ok": True,
        "rec_nsu": rec_nsu,
        "paid_amount": final_paid,
        "new_available_limit": new_available_limit,
        "receipt": receipt
    })


async def api_pos_limit_boost(request):
    """Prime WebPOS Express Credit Limit Increase at Store Counter."""
    data = await request.json()
    lead_id = int(data.get("lead_id"))
    requested_boost = float(data.get("boost_amount") or 500.0)
    operator_name = data.get("operator_name") or "Mesa WebPOS Loja"

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return web.json_response({"ok": False, "error": "Portador não encontrado."}, status=404)

    holder = dict(row)
    old_limit = float(holder["approved_limit"])
    new_limit = round(old_limit + requested_boost, 2)
    new_available = round(max(0.0, new_limit - float(holder["used_limit"])), 2)
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        UPDATE card_holders
        SET approved_limit = ?, lead_stage = CASE WHEN lead_stage = 'mesa_credito' THEN 'cartao_ativo' ELSE lead_stage END
        WHERE id = ?
    """, (new_limit, lead_id))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (NULL, ?, 'WebPOS Balcão', 'AUMENTO-LIMITE', ?, ?, ?, ?)
    """, (
        lead_id,
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Aumento Express de Limite no WebPOS aprovado por {operator_name}: de R$ {old_limit:,.2f} para R$ {new_limit:,.2f} (+R$ {requested_boost:,.2f}).",
        f"Novo Limite R$ {new_limit:,.2f}",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({
        "ok": True,
        "old_limit": old_limit,
        "new_limit": new_limit,
        "new_available_limit": new_available
    })


async def api_preview_message(request):
    data = await request.json()
    statement_id = data.get("statement_id")
    lead_id = data.get("lead_id")
    stage_code = data.get("stage_code")
    custom_tone = data.get("tone")

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    st_obj = None
    if statement_id:
        cur.execute("SELECT * FROM card_statements WHERE id = ?", (int(statement_id),))
        row = cur.fetchone()
        if row:
            st_obj = enrich_statement(dict(row), store)
            lead_id = st_obj["holder_id"]

    cur.execute("SELECT * FROM card_holders WHERE id = ?", (int(lead_id),))
    holder_row = cur.fetchone()
    if not holder_row:
        conn.close()
        return web.json_response({"error": "Portador não encontrado"}, status=404)
    holder_obj = dict(holder_row)

    if not stage_code:
        stage_code = st_obj["recommended_stage"] if st_obj else "ATIVACAO"

    cur.execute("SELECT * FROM collection_rules WHERE stage_code = ?", (stage_code,))
    rule_row = cur.fetchone()
    if not rule_row:
        cur.execute("SELECT * FROM collection_rules LIMIT 1")
        rule_row = cur.fetchone()
    rule = dict(rule_row)
    conn.close()

    subject = render_dm_template(rule["subject_template"], holder_obj, st_obj, store)
    body = render_dm_template(rule["message_template"], holder_obj, st_obj, store)

    return web.json_response({
        "statement": st_obj,
        "lead": holder_obj,
        "stage_code": rule["stage_code"],
        "channel": rule["channel"],
        "tone": custom_tone or rule["tone"],
        "subject": subject,
        "body": body,
        "whatsapp_url": f"https://wa.me/{holder_obj['whatsapp']}?text="
    })


async def api_send_collection(request):
    data = await request.json()
    statement_id = data.get("statement_id")
    lead_id = int(data.get("lead_id"))
    stage_code = data.get("stage_code", "D+3")
    channel = data.get("channel", "WhatsApp")
    message_body = data.get("message_body", "")
    outcome = data.get("outcome", "Enviado no WhatsApp do Cliente")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (lead_id,))
    holder = cur.fetchone()

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")
    recipient = f"{holder['full_name']} ({holder['whatsapp']})"

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (int(statement_id) if statement_id else None, lead_id, channel, stage_code, recipient, message_body, outcome, now_str))

    if statement_id:
        cur.execute("""
            UPDATE card_statements
            SET last_contact_at = ?, last_stage_sent = ?, contact_count = contact_count + 1
            WHERE id = ?
        """, (now_str, stage_code, int(statement_id)))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "timestamp": now_str})


async def api_dispatch_batch(request):
    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    cur.execute("SELECT * FROM card_statements WHERE status IN ('vencida', 'fechada', 'aberta')")
    rows = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM collection_rules")
    rules_map = {r["stage_code"]: dict(r) for r in cur.fetchall()}

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")
    dispatched = 0

    for st_raw in rows:
        if st_raw.get("promise_date"):
            continue
        st = enrich_statement(st_raw, store)
        stage_code = st["recommended_stage"]
        rule = rules_map.get(stage_code)
        if not rule or not rule.get("active", 1):
            continue

        cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
        holder = dict(cur.fetchone())
        body = render_dm_template(rule["message_template"], holder, st, store)

        cur.execute("""
            INSERT INTO interaction_logs (
                statement_id, holder_id, channel, stage_code, recipient,
                message_body, outcome, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            st["id"], holder["id"], rule["channel"], stage_code,
            f"{holder['full_name']} ({holder['whatsapp']})",
            body, f"Lote Régua Prime ({stage_code})", now_str
        ))
        cur.execute("""
            UPDATE card_statements
            SET last_contact_at = ?, last_stage_sent = ?, contact_count = contact_count + 1
            WHERE id = ?
        """, (now_str, stage_code, st["id"]))
        dispatched += 1

    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "dispatched_count": dispatched})


async def api_mark_paid(request):
    data = await request.json()
    statement_id = int(data.get("statement_id") or data.get("invoice_id"))
    paid_amount = data.get("paid_amount")

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_statements WHERE id = ?", (statement_id,))
    st_row = cur.fetchone()
    if not st_row:
        conn.close()
        return web.json_response({"error": "Fatura não encontrada"}, status=404)

    st = enrich_statement(dict(st_row), store)
    final_paid = float(paid_amount) if paid_amount is not None else st["updated_amount"]
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        UPDATE card_statements
        SET status = 'paga', paid_date = ?, paid_amount = ?
        WHERE id = ?
    """, (TODAY_STR, final_paid, statement_id))

    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = dict(cur.fetchone())
    restored_used = max(0.0, round(holder["used_limit"] - st["original_amount"], 2))
    new_score = min(995, holder["credit_score"] + 25)

    cur.execute("""
        UPDATE card_holders
        SET used_limit = ?, lead_stage = 'cartao_ativo', credit_score = ?
        WHERE id = ?
    """, (restored_used, new_score, holder["id"]))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'Conciliação PIX Prime', 'PIX-CONFIRMADO', ?, ?, ?, ?)
    """, (
        statement_id,
        holder["id"],
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Fatura {st['statement_code']} liquidada via PIX (R$ {final_paid:,.2f}). Limite recomposto e cartão DESBLOQUEADO no PDV!",
        "Pago + Cartão Liberado",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "paid_amount": final_paid})


async def api_register_promise(request):
    data = await request.json()
    statement_id = int(data.get("statement_id") or data.get("invoice_id"))
    promise_date = data.get("promise_date", "2026-10-18")
    promise_note = data.get("promise_note", "Cliente prometeu pagar via PIX no dia do pagamento.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_statements WHERE id = ?", (statement_id,))
    st = cur.fetchone()
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = cur.fetchone()
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")

    cur.execute("""
        UPDATE card_statements
        SET promise_date = ?, promise_note = ?, last_contact_at = ?
        WHERE id = ?
    """, (promise_date, promise_note, now_str, statement_id))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'Central de Cobrança Prime', 'PROMESSA', ?, ?, ?, ?)
    """, (
        statement_id, holder["id"],
        f"{holder['full_name']} (Final {holder['card_number_last4']})",
        f"Promessa de pagamento registrada para {promise_date}: {promise_note}",
        f"Promessa ({promise_date})",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def api_update_rule(request):
    data = await request.json()
    rule_id = data.get("id")
    conn = get_db()
    cur = conn.cursor()

    if rule_id:
        cur.execute("""
            UPDATE collection_rules
            SET title = ?, channel = ?, tone = ?, active = ?,
                subject_template = ?, message_template = ?
            WHERE id = ?
        """, (
            data.get("title"),
            data.get("channel"),
            data.get("tone"),
            1 if data.get("active", True) else 0,
            data.get("subject_template"),
            data.get("message_template"),
            int(rule_id)
        ))
    else:
        cur.execute("""
            INSERT INTO collection_rules (
                day_offset, stage_code, title, channel, tone, active,
                subject_template, message_template
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            int(data.get("day_offset", 10)),
            data.get("stage_code", "D+10"),
            data.get("title", "Nova Regra do Cartão"),
            data.get("channel", "WhatsApp"),
            data.get("tone", "amigavel"),
            data.get("subject_template", "Aviso Cartão {{nome_cartao}}"),
            data.get("message_template", "Olá {{cliente}}, sua fatura {{fatura}} está em {{valor_atualizado}}. Acesse: {{link_portal}}")
        ))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def api_create_agreement(request):
    data = await request.json()
    statement_id = int(data.get("statement_id") or data.get("invoice_id"))
    discount_pct = float(data.get("discount_pct", 80.0))
    installments = int(data.get("installments", 3))
    down_payment_pct = float(data.get("down_payment_pct", 30.0))
    first_due_date = data.get("first_due_date", "2026-10-16")

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_statements WHERE id = ?", (statement_id,))
    st_row = cur.fetchone()
    st = enrich_statement(dict(st_row), store)
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = dict(cur.fetchone())

    discounted_charges = st["total_charges"] * (1.0 - (discount_pct / 100.0))
    final_amount = round(st["original_amount"] + discounted_charges, 2)

    if installments <= 1:
        down_payment = final_amount
        installment_value = final_amount
    else:
        down_payment = round(final_amount * (down_payment_pct / 100.0), 2)
        installment_value = round((final_amount - down_payment) / (installments - 1), 2)

    agreement_code = f"PARC-PR/{statement_id:02d}{datetime.datetime.now().strftime('%M%S')}"
    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M")
    sig_hash = hashlib.sha256(f"{agreement_code}|{holder['cpf']}|{final_amount}".encode()).hexdigest()[:20].upper()

    cur.execute("""
        INSERT INTO card_agreements (
            agreement_code, statement_id, holder_id, original_amount, updated_amount,
            discount_pct, final_amount, installments, down_payment,
            installment_value, first_due_date, status,
            signer_name, signer_cpf, signer_ip, signature_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Parcelamento Ativo', ?, ?, 'Balcão / Painel Loja', ?, ?)
    """, (
        agreement_code, statement_id, holder["id"], st["original_amount"], st["updated_amount"],
        discount_pct, final_amount, installments, down_payment,
        installment_value, first_due_date,
        holder["full_name"], holder["cpf"], sig_hash, now_str
    ))

    cur.execute("""
        UPDATE card_statements
        SET status = 'acordo', last_contact_at = ?, last_stage_sent = 'ACORDO-FATURA'
        WHERE id = ?
    """, (now_str, statement_id))

    cur.execute("""
        UPDATE card_holders
        SET lead_stage = 'cartao_ativo'
        WHERE id = ?
    """, (holder["id"],))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'Parcelamento de Fatura Prime', 'PARCELAMENTO', ?, ?, ?, ?)
    """, (
        statement_id, holder["id"],
        f"{holder['full_name']} (CPF {holder['cpf']})",
        f"Acordo {agreement_code} fechado em {installments}x (Total R$ {final_amount:,.2f}). Cartão reabilitado no PDV!",
        f"Acordo {agreement_code}",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "agreement_code": agreement_code})


async def api_update_store(request):
    data = await request.json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE store_settings
        SET store_name = ?,
            card_brand_name = ?,
            cnpj = ?,
            pix_key = ?,
            support_whatsapp = ?,
            anuidade_faturada_brl = ?,
            seguro_protegido_brl = ?,
            sms_alerta_brl = ?,
            comissao_promotor_brl = ?,
            comissao_seguro_brl = ?,
            fine_pct = ?,
            rotativo_interest_pct = ?,
            crediario_interest_pct = ?,
            min_score_auto_approve = ?,
            auto_block_days = ?,
            first_purchase_discount_pct = ?,
            brand_color = ?
        WHERE id = 1
    """, (
        data.get("store_name", "Armarinhos Fernando Ltda."),
        data.get("card_brand_name", "Cartão Armarinhos Fernando"),
        data.get("cnpj", "24.890.100/0001-60"),
        data.get("pix_key", "faturas@armarinhosfernando.com.br"),
        data.get("support_whatsapp", "5511980005544"),
        float(data.get("anuidade_faturada_brl", 14.90)),
        float(data.get("seguro_protegido_brl", 9.90)),
        float(data.get("sms_alerta_brl", 5.90)),
        float(data.get("comissao_promotor_brl", 6.00)),
        float(data.get("comissao_seguro_brl", 3.50)),
        float(data.get("fine_pct", 2.0)),
        float(data.get("rotativo_interest_pct", 11.9)),
        float(data.get("crediario_interest_pct", 4.99)),
        int(data.get("min_score_auto_approve", 550)),
        int(data.get("auto_block_days", 5)),
        float(data.get("first_purchase_discount_pct", 10.0)),
        data.get("brand_color", "#d4af37"),
    ))
    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def api_portal_statement(request):
    st_id = int(request.match_info.get("statement_id", 1))
    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()

    cur.execute("SELECT * FROM card_statements WHERE id = ?", (st_id,))
    st_row = cur.fetchone()
    if not st_row:
        cur.execute("SELECT * FROM card_statements ORDER BY id ASC LIMIT 1")
        st_row = cur.fetchone()

    st = enrich_statement(dict(st_row), store)
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = dict(cur.fetchone())
    holder["available_limit"] = round(max(0.0, holder["approved_limit"] - holder["used_limit"]), 2)

    cur.execute("SELECT * FROM pos_transactions WHERE holder_id = ? ORDER BY id DESC LIMIT 10", (holder["id"],))
    txs = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM card_agreements WHERE statement_id = ? ORDER BY id DESC LIMIT 1", (st["id"],))
    existing_ag = cur.fetchone()
    conn.close()

    charges = st["total_charges"]
    orig = st["original_amount"]

    plans = [
        {
            "plan_id": "pix_cash",
            "title": "Pagar Fatura à Vista no PIX (Libera Limite na Hora!)",
            "badge": "⚡ 95% OFF nos Juros do Rotativo",
            "discount_pct": 95.0,
            "installments": 1,
            "final_amount": round(orig + charges * 0.05, 2),
            "down_payment": round(orig + charges * 0.05, 2),
            "installment_value": round(orig + charges * 0.05, 2),
            "savings": round(charges * 0.95, 2),
        },
        {
            "plan_id": "parcelado_3x",
            "title": "Parcelar Fatura em 3x Fixas (Entrada PIX + 2x)",
            "badge": "💳 60% OFF nos Juros • Desbloqueia Cartão",
            "discount_pct": 60.0,
            "installments": 3,
            "final_amount": round(orig + charges * 0.40, 2),
            "down_payment": round((orig + charges * 0.40) / 3.0, 2),
            "installment_value": round((orig + charges * 0.40) / 3.0, 2),
            "savings": round(charges * 0.60, 2),
        },
        {
            "plan_id": "parcelado_6x",
            "title": "Parcelar Fatura em 6x (Parcela que cabe no bolso)",
            "badge": "🤝 Entrada Reduzida + 5x na Fatura",
            "discount_pct": 25.0,
            "installments": 6,
            "final_amount": round(orig + charges * 0.75, 2),
            "down_payment": round((orig + charges * 0.75) * 0.20, 2),
            "installment_value": round(((orig + charges * 0.75) * 0.80) / 5.0, 2),
            "savings": round(charges * 0.25, 2),
        },
    ]

    qr_svg = generate_qr_svg(st.get("pix_key") or store["pix_key"])

    return web.json_response({
        "store": store,
        "statement": st,
        "lead": holder,
        "transactions": txs,
        "plans": plans,
        "qr_svg": qr_svg,
        "existing_agreement": dict(existing_ag) if existing_ag else None
    })


async def api_portal_accept(request):
    st_id = int(request.match_info.get("statement_id", 1))
    data = await request.json()
    signer_name = (data.get("signer_name") or "Titular do Cartão").strip()
    signer_cpf = (data.get("signer_cpf") or data.get("signer_doc") or "000.000.000-00").strip()
    discount_pct = float(data.get("discount_pct", 95.0))
    installments = int(data.get("installments", 1))
    final_amount = float(data.get("final_amount", 0.0))
    down_payment = float(data.get("down_payment", 0.0))
    installment_value = float(data.get("installment_value", 0.0))

    conn = get_db()
    store = get_store_settings(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM card_statements WHERE id = ?", (st_id,))
    st_row = cur.fetchone()
    st = enrich_statement(dict(st_row), store)
    cur.execute("SELECT * FROM card_holders WHERE id = ?", (st["holder_id"],))
    holder = dict(cur.fetchone())

    now_str = "2026-10-14 " + datetime.datetime.now().strftime("%H:%M:%S")
    signer_ip = request.headers.get("X-Forwarded-For", "189.40.112.90")
    raw_sig = f"{st_id}|{holder['cpf']}|{signer_name}|{final_amount}|{now_str}"
    signature_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:24].upper()
    agreement_code = f"APP-PR/{st_id:02d}{datetime.datetime.now().strftime('%M%S')}"

    cur.execute("""
        INSERT INTO card_agreements (
            agreement_code, statement_id, holder_id, original_amount, updated_amount,
            discount_pct, final_amount, installments, down_payment,
            installment_value, first_due_date, status,
            signer_name, signer_cpf, signer_ip, signature_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Assinado no Super App', ?, ?, ?, ?, ?)
    """, (
        agreement_code, st_id, holder["id"], st["original_amount"], st["updated_amount"],
        discount_pct, final_amount, installments, down_payment,
        installment_value, TODAY_STR,
        signer_name, signer_cpf, signer_ip, signature_hash, now_str
    ))

    cur.execute("""
        UPDATE card_statements
        SET status = 'acordo', last_contact_at = ?, last_stage_sent = 'APP-ACEITE'
        WHERE id = ?
    """, (now_str, st_id))

    cur.execute("""
        UPDATE card_holders
        SET lead_stage = 'cartao_ativo'
        WHERE id = ?
    """, (holder["id"],))

    cur.execute("""
        INSERT INTO interaction_logs (
            statement_id, holder_id, channel, stage_code, recipient,
            message_body, outcome, created_at
        ) VALUES (?, ?, 'Super App do Cliente', 'ACEITE-PORTADOR', ?, ?, ?, ?)
    """, (
        st_id, holder["id"],
        f"{signer_name} (CPF {signer_cpf})",
        f"Acordo {agreement_code} assinado pelo cliente no App ({installments}x, R$ {final_amount:,.2f}). Cartão desbloqueado no PDV!",
        f"Acordo no App ({agreement_code})",
        now_str
    ))

    conn.commit()
    conn.close()
    return web.json_response({
        "ok": True,
        "agreement_code": agreement_code,
        "signature_hash": signature_hash,
        "signed_at": now_str,
        "signer_ip": signer_ip
    })


def _pub_file(fname):
    p1 = os.path.join(PUBLIC_DIR, fname)
    if os.path.exists(p1):
        return p1
    return os.path.join(BASE_DIR, fname)


async def index_handler(request):
    return web.FileResponse(_pub_file("index.html"))


async def portal_page_handler(request):
    return web.FileResponse(_pub_file("portal.html"))


async def webpos_page_handler(request):
    return web.FileResponse(_pub_file("webpos.html"))


async def cadastro_page_handler(request):
    return web.FileResponse(_pub_file("cadastro.html"))


async def styles_css_handler(request):
    return web.FileResponse(_pub_file("styles.css"))


async def app_js_handler(request):
    return web.FileResponse(_pub_file("app.js"))


async def api_auth_login(request):
    """Authenticates strictly with the customer's own CPF and Password registered by the store consultant."""
    data = await request.json()
    mode = data.get("mode", "cliente")
    identifier = (data.get("cpf") or data.get("identifier") or "").strip()
    password = (data.get("password") or "").strip()

    if not identifier:
        return web.json_response({"ok": False, "error": "Informe o seu CPF para entrar."}, status=400)
    if not password:
        return web.json_response({"ok": False, "error": "Informe a sua senha para entrar."}, status=400)

    conn = get_db()
    cur = conn.cursor()

    if mode == "cliente":
        clean_cpf = "".join(ch for ch in identifier if ch.isdigit())
        if len(clean_cpf) < 11:
            conn.close()
            return web.json_response({"ok": False, "error": "Digite os 11 dígitos do seu CPF."}, status=400)

        cur.execute("SELECT * FROM card_holders ORDER BY id DESC")
        rows = [dict(r) for r in cur.fetchall()]
        matched = None
        for r in rows:
            r_cpf = "".join(ch for ch in (r["cpf"] or "") if ch.isdigit())
            if r_cpf == clean_cpf:
                matched = r
                break

        if not matched:
            conn.close()
            return web.json_response({
                "ok": False,
                "error": "CPF não cadastrado. Faça seu cadastro com uma consultora da loja para acessar o aplicativo."
            }, status=404)

        expected_pass = str(matched.get("card_pin") or "").strip()
        if password != expected_pass:
            conn.close()
            return web.json_response({
                "ok": False,
                "error": "Senha incorreta para este CPF. Verifique a senha cadastrada com a consultora."
            }, status=401)

        conn.close()
        return web.json_response({
            "ok": True,
            "holder": matched,
            "message": f"Bem-vindo(a), {matched['full_name']}!"
        })

    if mode == "admin":
        clean_cpf = "".join(ch for ch in identifier if ch.isdigit())
        if len(clean_cpf) < 11:
            conn.close()
            return web.json_response({"ok": False, "error": "Digite os 11 dígitos do CPF do colaborador."}, status=400)

        cur.execute("SELECT * FROM admin_users ORDER BY id DESC")
        rows = [dict(r) for r in cur.fetchall()]
        matched_admin = None
        for r in rows:
            r_cpf = "".join(ch for ch in (r["cpf"] or "") if ch.isdigit())
            if r_cpf == clean_cpf:
                matched_admin = r
                break

        if not matched_admin:
            conn.close()
            return web.json_response({
                "ok": False,
                "error": "CPF não cadastrado na equipe administrativa. Solicite seu cadastro ao Adm Geral."
            }, status=404)

        if matched_admin.get("status") != "ativo":
            conn.close()
            return web.json_response({
                "ok": False,
                "error": "Acesso bloqueado pelo Adm Geral. Entre em contato com a diretoria."
            }, status=403)

        expected_pass = str(matched_admin.get("password") or "").strip()
        if password != expected_pass:
            conn.close()
            return web.json_response({
                "ok": False,
                "error": "Senha incorreta para este CPF administrativo."
            }, status=401)

        conn.close()
        role_labels = {
            "adm_geral": "🛡️ Adm Geral (Acesso Total)",
            "credito": "💳 Mesa de Crédito (Acesso Restrito: Crédito)",
            "cobranca": "📞 Setor de Cobrança (Acesso Restrito: Cobrança)"
        }
        matched_admin["role_label"] = role_labels.get(matched_admin["role"], matched_admin["role"])
        return web.json_response({
            "ok": True,
            "admin_user": matched_admin,
            "message": f"Bem-vindo(a), {matched_admin['full_name']} ({matched_admin['role_label']})!"
        })

    conn.close()
    return web.json_response({
        "ok": True,
        "user": {
            "cpf": identifier,
            "role": mode
        }
    })


async def api_create_admin_user(request):
    data = await request.json()
    full_name = (data.get("full_name") or "").strip()
    cpf = (data.get("cpf") or "").strip()
    password = (data.get("password") or "").strip()
    role = (data.get("role") or "cobranca").strip()
    department = (data.get("department") or "").strip()
    branch = (data.get("branch") or "Matriz Centro").strip()

    if not full_name or not cpf or not password:
        return web.json_response({"ok": False, "error": "Preencha Nome, CPF e Senha."}, status=400)

    clean_cpf = "".join(ch for ch in cpf if ch.isdigit())
    if len(clean_cpf) < 11:
        return web.json_response({"ok": False, "error": "Digite os 11 dígitos do CPF."}, status=400)
    cpf_fmt = f"{clean_cpf[:3]}.{clean_cpf[3:6]}.{clean_cpf[6:9]}-{clean_cpf[9:11]}"

    if role not in ("adm_geral", "credito", "cobranca"):
        role = "cobranca"

    if not department:
        dept_map = {
            "adm_geral": "Administração Geral Master",
            "credito": "Mesa de Crédito & Limites",
            "cobranca": "Central de Cobrança & Acordos"
        }
        department = dept_map.get(role, "Operações")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM admin_users WHERE replace(replace(cpf, '.', ''), '-', '') = ?",
        (clean_cpf,)
    )
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("""
        INSERT INTO admin_users (full_name, cpf, password, role, department, branch, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'ativo', ?)
    """, (full_name, cpf_fmt, password, role, department, branch, now_str))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return web.json_response({"ok": True, "id": new_id})


async def api_update_admin_user(request):
    data = await request.json()
    uid = data.get("id")
    if not uid:
        return web.json_response({"ok": False, "error": "ID obrigatório"}, status=400)

    conn = get_db()
    cur = conn.cursor()
    if "role" in data:
        role = data["role"]
        dept_map = {
            "adm_geral": "Administração Geral Master",
            "credito": "Mesa de Crédito & Limites",
            "cobranca": "Central de Cobrança & Acordos"
        }
        cur.execute("UPDATE admin_users SET role = ?, department = ? WHERE id = ?", (role, dept_map.get(role, "Operações"), uid))
    if "password" in data and str(data["password"]).strip():
        cur.execute("UPDATE admin_users SET password = ? WHERE id = ?", (str(data["password"]).strip(), uid))
    if "status" in data:
        cur.execute("UPDATE admin_users SET status = ? WHERE id = ?", (data["status"], uid))
    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def api_delete_admin_user(request):
    data = await request.json()
    uid = data.get("id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    return web.json_response({"ok": True})


async def forbidden_client_handler(request):
    return web.json_response({
        "ok": False,
        "error": "ACESSO BLOQUEADO (403): O Super App do Cliente é estritamente isolado e NUNCA possui acesso ao WebPOS ou ao Painel do Administrador."
    }, status=403)


async def api_sync_version(request):
    """Returns real-time hashes of Database state and Code files so all open external browser tabs sync automatically."""
    sandbox_id = os.environ.get("E2B_SANDBOX_ID", "ip7iniu5khmvczt5y3hcc")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(used_limit),0), COALESCE(SUM(approved_limit),0) FROM card_holders")
    h_stat = cur.fetchone()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(paid_amount),0) FROM card_statements WHERE status = 'paga'")
    s_stat = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM interaction_logs")
    l_stat = cur.fetchone()
    cur.execute("SELECT store_name, card_brand_name, brand_color, anuidade_faturada_brl, seguro_protegido_brl, rotativo_interest_pct, crediario_interest_pct, comissao_promotor_brl, comissao_seguro_brl FROM store_settings WHERE id = 1")
    st_row = cur.fetchone()
    conn.close()

    db_mtime = os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0
    raw_db = f"{db_mtime}|{tuple(h_stat)}|{tuple(s_stat)}|{tuple(l_stat)}|{tuple(st_row) if st_row else ''}"
    db_version = hashlib.md5(raw_db.encode("utf-8")).hexdigest()[:12]

    code_files = ["index.html", "app.js", "webpos.html", "portal.html", "cadastro.html", "styles.css"]
    mtimes = []
    for fname in code_files:
        fpath = os.path.join(PUBLIC_DIR, fname)
        if os.path.exists(fpath):
            mtimes.append(f"{fname}:{int(os.path.getmtime(fpath))}")
    code_version = hashlib.md5("|".join(mtimes).encode("utf-8")).hexdigest()[:12]

    def read_pub_url(r_name, fallback_port):
        p = os.path.join(DATA_DIR, f"url_{r_name}.txt")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    return val
        render_base = (os.environ.get("RENDER_EXTERNAL_URL") or "https://armarinhosfernando-card.onrender.com").rstrip("/")
        path_map = {
            "admin": f"{render_base}/",
            "webpos": f"{render_base}/webpos",
            "cliente": f"{render_base}/portal",
            "cadastro": f"{render_base}/cadastro"
        }
        return path_map.get(r_name, render_base)

    return web.json_response({
        "ok": True,
        "db_version": db_version,
        "code_version": code_version,
        "keepalive": KEEPALIVE_INFO,
        "external_domains": {
            "admin_domain": "https://admarmarinhosfernando.com",
            "webpos_domain": "https://webposarmarinhosfernando.com",
            "cadastro_domain": "https://promotorarmarinhosfernando.com",
            "client_app_domain": "https://apparmarinhosfernando.com"
        },
        "external_links": {
            "admin_url": read_pub_url("admin", 3000),
            "webpos_url": read_pub_url("webpos", 3001),
            "client_app_url": read_pub_url("cliente", 3002),
            "cadastro_url": read_pub_url("cadastro", 3003)
        }
    })


KEEPALIVE_INFO = {
    "active": True,
    "interval_minutes": 10,
    "last_ping_at": datetime.datetime.now().strftime("%H:%M:%S"),
    "cycle_count": 1,
}


def _keepalive_worker():
    import time
    import urllib.request

    cycle = 0
    last_synced_mtime = 0
    while True:
        time.sleep(60)
        cycle += 1
        KEEPALIVE_INFO["last_ping_at"] = datetime.datetime.now().strftime("%H:%M:%S")
        KEEPALIVE_INFO["cycle_count"] = cycle
        try:
            cur_mtime = int(os.path.getmtime(DB_PATH)) if os.path.exists(DB_PATH) else 0
            if cur_mtime != last_synced_mtime:
                last_synced_mtime = cur_mtime
                import auto_sync_github
                auto_sync_github.sync_to_github("Auto-Sync Arena -> GitHub")
        except Exception:
            pass
        for p_num in (3000, 3001, 3002, 3003):
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{p_num}/api/sync-version?keepalive=1", timeout=5
                ).read()
            except Exception:
                pass
        # Faz ping externo na URL pública do Render para nunca hibernar
        render_ext_url = (os.environ.get("RENDER_EXTERNAL_URL") or "https://armarinhosfernando-card.onrender.com").strip().rstrip("/")
        if render_ext_url.startswith("https://"):
            try:
                req_r = urllib.request.Request(
                    f"{render_ext_url}/api/sync-version?keepalive=1&c={cycle}",
                    headers={"User-Agent": "ArmarinhosFernando-Render-KeepAlive/1.0"},
                )
                urllib.request.urlopen(req_r, timeout=10).read()
            except Exception:
                pass
        for r_name in ("admin", "webpos", "cliente", "cadastro"):
            try:
                p_file = os.path.join(DATA_DIR, f"url_{r_name}.txt")
                if os.path.exists(p_file):
                    with open(p_file, "r", encoding="utf-8") as f:
                        pub_url = f.read().strip()
                    if pub_url.startswith("https://"):
                        req = urllib.request.Request(
                            f"{pub_url}/api/sync-version?keepalive=1&c={cycle}",
                            headers={"User-Agent": "Armarinhos Fernando-KeepAlive-10m/1.0"},
                        )
                        urllib.request.urlopen(req, timeout=10).read()
            except Exception:
                pass


@web.middleware
async def cors_and_frame_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=200)
    else:
        host_hdr = (request.headers.get("Host") or "").lower()
        if request.path == "/":
            if "webposarmarinhosfernando.com" in host_hdr:
                resp = await webpos_page_handler(request)
            elif "promotorarmarinhosfernando.com" in host_hdr:
                resp = await cadastro_page_handler(request)
            elif "admarmarinhosfernando.com" in host_hdr:
                resp = await index_handler(request)
            elif "apparmarinhosfernando.com" in host_hdr:
                resp = await portal_page_handler(request)
            else:
                resp = await handler(request)
        else:
            resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def create_app(role="admin"):
    import threading

    init_db()
    threading.Thread(target=_keepalive_worker, daemon=True).start()
    app = web.Application(middlewares=[cors_and_frame_middleware])

    if role == "cliente":
        # Customer Super App ONLY — WebPOS and Admin UI are strictly blocked!
        app.router.add_get("/", portal_page_handler)
        app.router.add_get("/portal", portal_page_handler)
        app.router.add_get("/webpos", forbidden_client_handler)
        app.router.add_get("/cadastro", forbidden_client_handler)
        app.router.add_post("/api/pos-purchase", forbidden_client_handler)
        app.router.add_post("/api/pos-reverse", forbidden_client_handler)
        app.router.add_post("/api/pos-pay-invoice", forbidden_client_handler)
        app.router.add_post("/api/pos-limit-boost", forbidden_client_handler)
    elif role == "webpos":
        # Dedicated Store Cashier WebPOS Terminal
        app.router.add_get("/", webpos_page_handler)
        app.router.add_get("/webpos", webpos_page_handler)
        app.router.add_get("/cadastro", cadastro_page_handler)
        app.router.add_get("/portal", portal_page_handler)
        app.router.add_post("/api/pos-purchase", api_pos_purchase)
        app.router.add_post("/api/pos-reverse", api_pos_reverse)
        app.router.add_post("/api/pos-pay-invoice", api_pos_pay_invoice)
        app.router.add_post("/api/pos-limit-boost", api_pos_limit_boost)
    elif role == "cadastro":
        # Dedicated Collaborator / Promoter Customer Registration & Credit Pipeline Portal
        app.router.add_get("/", cadastro_page_handler)
        app.router.add_get("/cadastro", cadastro_page_handler)
        app.router.add_get("/portal", portal_page_handler)
        app.router.add_post("/api/pos-purchase", api_pos_purchase)
        app.router.add_post("/api/pos-limit-boost", api_pos_limit_boost)
    else:
        # Master Card Administrator — Can see and operate EVERYTHING
        app.router.add_get("/", index_handler)
        app.router.add_get("/portal", portal_page_handler)
        app.router.add_get("/webpos", webpos_page_handler)
        app.router.add_get("/cadastro", cadastro_page_handler)
        app.router.add_post("/api/pos-purchase", api_pos_purchase)
        app.router.add_post("/api/pos-reverse", api_pos_reverse)
        app.router.add_post("/api/pos-pay-invoice", api_pos_pay_invoice)
        app.router.add_post("/api/pos-limit-boost", api_pos_limit_boost)

    app.router.add_get("/styles.css", styles_css_handler)
    app.router.add_get("/static/styles.css", styles_css_handler)
    app.router.add_get("/app.js", app_js_handler)
    app.router.add_get("/static/app.js", app_js_handler)
    app.router.add_post("/api/auth/login", api_auth_login)
    app.router.add_post("/api/admin-users", api_create_admin_user)
    app.router.add_post("/api/admin-users/update", api_update_admin_user)
    app.router.add_post("/api/admin-users/delete", api_delete_admin_user)
    app.router.add_get("/api/state", api_state)
    app.router.add_get("/api/sync-version", api_sync_version)
    app.router.add_get("/api/cep", api_lookup_cep)
    app.router.add_post("/api/leads", api_create_lead)
    app.router.add_post("/api/leads/whatsapp-config", api_send_whatsapp_card_config)
    app.router.add_post("/api/leads/stage", api_update_lead_stage)
    app.router.add_post("/api/leads/update-holder", api_update_holder)
    app.router.add_post("/api/preview-message", api_preview_message)
    app.router.add_post("/api/send-collection", api_send_collection)
    app.router.add_post("/api/dispatch-batch", api_dispatch_batch)
    app.router.add_post("/api/mark-paid", api_mark_paid)
    app.router.add_post("/api/statements/pay", api_mark_paid)
    app.router.add_post("/api/register-promise", api_register_promise)
    app.router.add_post("/api/statements/promise", api_register_promise)
    app.router.add_post("/api/rules", api_update_rule)
    app.router.add_post("/api/agreements", api_create_agreement)
    app.router.add_post("/api/store", api_update_store)
    app.router.add_get("/api/portal/{statement_id}", api_portal_statement)
    app.router.add_post("/api/portal/{statement_id}/accept", api_portal_accept)
    app.router.add_static("/static", PUBLIC_DIR, show_index=False)
    return app


if __name__ == "__main__":
    import sys
    role_arg = os.environ.get("ROLE", "admin")
    port_arg = int(os.environ.get("PORT", "3000"))
    for arg in sys.argv[1:]:
        if arg.startswith("--role="):
            role_arg = arg.split("=", 1)[1]
        elif arg.startswith("--port="):
            port_arg = int(arg.split("=", 1)[1])
    app = create_app(role=role_arg)
    web.run_app(app, host="0.0.0.0", port=port_arg)

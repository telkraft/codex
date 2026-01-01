"""
services/email_service.py
=========================

Email Service - Mevcut n8n workflow'unu kullanır.

Telkraft'ın mevcut n8n email yapısını kullanarak:
- Webhook → Validate Data → Send email → Respond

Backend sadece HTML oluşturur ve n8n webhook'u çağırır.
"""

from __future__ import annotations
import os
import re
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - Mevcut n8n webhook'unu kullan
# ============================================================================

N8N_EMAIL_WEBHOOK = os.getenv(
    "N8N_EMAIL_WEBHOOK", 
    "https://n8n.promptever.com/webhook/promptever-email"
)

# MongoDB (opsiyonel - sadece schedules/alerts için)
try:
    from config import mongo_client, MONGO_DB_NAME
    db = mongo_client[MONGO_DB_NAME]
    schedules_collection = db["email_schedules"]
    alerts_collection = db["email_alerts"]
    logs_collection = db["email_logs"]
    HAS_MONGO = True
except:
    HAS_MONGO = False
    logger.warning("MongoDB bağlantısı yok, sadece instant email çalışacak")


# ============================================================================
# MARKDOWN TO HTML CONVERTER
# ============================================================================

def markdown_to_html(text: str) -> str:
    """
    Basit markdown → HTML dönüştürücü.
    LLM çıktılarındaki temel markdown formatlarını destekler.
    """
    if not text:
        return ""
    
    # Escape HTML karakterleri (güvenlik)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Headers: ## Header → <h3>Header</h3>
    text = re.sub(r'^### (.+)$', r'<h4 style="color: #374151; margin: 16px 0 8px 0; font-size: 14px;">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h3 style="color: #1e40af; margin: 20px 0 12px 0; font-size: 16px; font-weight: 600;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h2 style="color: #1e40af; margin: 24px 0 12px 0; font-size: 18px; font-weight: 700;">\1</h2>', text, flags=re.MULTILINE)
    
    # Bold: **text** → <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    
    # Italic: *text* → <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    
    # Bullet lists: * item → <li>item</li>
    lines = text.split('\n')
    result_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('* ') or stripped.startswith('- '):
            if not in_list:
                result_lines.append('<ul style="margin: 12px 0; padding-left: 24px;">')
                in_list = True
            item_text = stripped[2:]
            result_lines.append(f'<li style="margin: 6px 0; color: #4b5563;">{item_text}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    
    if in_list:
        result_lines.append('</ul>')
    
    text = '\n'.join(result_lines)
    
    # Numbered lists: 1. item → <li>item</li>
    text = re.sub(r'^\d+\.\s+(.+)$', r'<li style="margin: 6px 0; color: #4b5563;">\1</li>', text, flags=re.MULTILINE)
    
    # Code inline: `code` → <code>code</code>
    text = re.sub(r'`([^`]+)`', r'<code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px;">\1</code>', text)
    
    # Paragraphs: Double newlines → </p><p>
    text = re.sub(r'\n\n+', '</p><p style="margin: 12px 0; line-height: 1.7;">', text)
    
    # Single newlines → <br>
    text = re.sub(r'\n', '<br>', text)
    
    # Wrap in paragraph if not already
    if not text.startswith('<'):
        text = f'<p style="margin: 12px 0; line-height: 1.7;">{text}</p>'
    
    return text


# ============================================================================
# HTML EMAIL TEMPLATE
# ============================================================================

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        .header {{
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }}
        .header h1 {{
            color: #1e40af;
            margin: 0;
            font-size: 24px;
        }}
        .meta {{
            color: #6b7280;
            font-size: 14px;
            margin-top: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 8px;
        }}
        .badge-intent {{ background-color: #dbeafe; color: #1e40af; }}
        .badge-scenario {{ background-color: #dcfce7; color: #166534; }}
        .section {{
            margin-bottom: 25px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 600;
            color: #374151;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .llm-answer {{
            background-color: #f0f9ff;
            border-left: 4px solid #3b82f6;
            padding: 20px 24px;
            border-radius: 0 8px 8px 0;
            color: #1e3a5f;
        }}
        .llm-answer h2, .llm-answer h3, .llm-answer h4 {{
            margin-top: 0;
        }}
        .llm-answer p:first-child {{
            margin-top: 0;
        }}
        .llm-answer p:last-child {{
            margin-bottom: 0;
        }}
        .note-box {{
            background-color: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px 20px;
            border-radius: 0 8px 8px 0;
            color: #92400e;
        }}
        .query-box {{
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 10px 0;
            color: #1e293b;
            font-size: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 14px;
        }}
        th {{
            background-color: #f8fafc;
            color: #475569;
            font-weight: 600;
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #e2e8f0;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        tr:hover td {{ background-color: #f8fafc; }}
        tr:nth-child(even) td {{ background-color: #fafafa; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-card {{
            background-color: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: 700;
            color: #1e40af;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            margin-top: 4px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #9ca3af;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


def generate_chat_email_html(
    query_text: str,
    chat_response: Dict[str, Any],
    include_tables: bool = True,
    include_llm_answer: bool = True,
    include_statistics: bool = True,
    report_name: Optional[str] = None,
    user_note: Optional[str] = None,
) -> str:
    """
    Chat response'dan HTML email içeriği oluştur.
    
    Sıralama:
    1. Header (Başlık, Intent, Scenario, Tarih)
    2. Sorgu
    3. Not/Açıklama (varsa)
    4. LLM Yorumu (varsa ve isteniyorsa)
    5. Tablolar
    6. Footer
    """
    
    intent = chat_response.get("intent", "unknown")
    scenario = chat_response.get("scenario", "")
    
    # =========================================================================
    # 1. HEADER
    # =========================================================================
    title = report_name or "Sorgu Sonucu"
    content = f"""
    <div class="header">
        <h1>📊 {title}</h1>
        <div class="meta">
            <span class="badge badge-intent">Intent: {intent}</span>
            {f'<span class="badge badge-scenario">{scenario}</span>' if scenario else ''}
        </div>
        <div class="meta" style="margin-top: 12px;">
            <strong>Tarih:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </div>
    </div>
    """
    
    # =========================================================================
    # 2. SORGU
    # =========================================================================
    content += f"""
    <div class="section">
        <div class="section-title">🔍 Sorgu</div>
        <div class="query-box">
            {query_text}
        </div>
    </div>
    """
    
    # =========================================================================
    # 3. NOT / AÇIKLAMA (varsa)
    # =========================================================================
    if user_note and user_note.strip():
        content += f"""
    <div class="section">
        <div class="section-title">📝 Not</div>
        <div class="note-box">
            {user_note}
        </div>
    </div>
        """
    
    # =========================================================================
    # 4. LLM YORUMU (varsa ve isteniyorsa)
    # =========================================================================
    if include_llm_answer:
        llm_data = chat_response.get("llm", {})
        llm_answer = chat_response.get("answer") or llm_data.get("answer", "")
        
        if llm_answer:
            # Markdown'ı HTML'e çevir
            formatted_answer = markdown_to_html(llm_answer)
            
            content += f"""
    <div class="section">
        <div class="section-title">🤖 LLM Yorumu</div>
        <div class="llm-answer">
            {formatted_answer}
        </div>
    </div>
            """
    
    # =========================================================================
    # 5. İSTATİSTİKLER (varsa)
    # =========================================================================
    if include_statistics and chat_response.get("statistics"):
        stats = chat_response["statistics"]
        stats_html = '<div class="stats-grid">'
        
        stat_labels = {
            "total_count": "Toplam Kayıt",
            "total_vehicles": "Araç Sayısı",
            "total_cost": "Toplam Maliyet",
            "avg_cost": "Ort. Maliyet",
            "unique_materials": "Benzersiz Malzeme",
            "unique_vehicles": "Benzersiz Araç",
            "avg_per_vehicle": "Araç Başına Ort.",
            "min_value": "Min Değer",
            "max_value": "Max Değer",
        }
        
        for key, value in stats.items():
            if key.startswith("_"):
                continue
            label = stat_labels.get(key, key.replace("_", " ").title())
            
            if isinstance(value, (int, float)):
                if "cost" in key.lower() or "maliyet" in key.lower():
                    display_value = f"₺{value:,.2f}"
                elif isinstance(value, float):
                    display_value = f"{value:,.2f}"
                else:
                    display_value = f"{value:,}"
            else:
                display_value = str(value)
            
            stats_html += f"""
            <div class="stat-card">
                <div class="stat-value">{display_value}</div>
                <div class="stat-label">{label}</div>
            </div>
            """
        
        stats_html += '</div>'
        
        content += f"""
    <div class="section">
        <div class="section-title">📈 İstatistikler</div>
        {stats_html}
    </div>
        """
    
    # =========================================================================
    # 6. TABLOLAR
    # =========================================================================
    if include_tables and chat_response.get("tables"):
        for table in chat_response["tables"]:
            table_title = table.get("title", "Veri Tablosu")
            table_desc = table.get("description", "")
            columns = table.get("columns", [])
            rows = table.get("rows", [])
            
            # Maximum 30 satır göster (email boyutu için)
            max_rows = 30
            showing = min(len(rows), max_rows)
            total = len(rows)
            display_rows = rows[:max_rows]
            
            # Tablo HTML'i oluştur
            table_html = '<table>'
            
            # Header
            table_html += '<thead><tr>'
            table_html += '<th style="width: 40px;">#</th>'
            for col in columns:
                table_html += f'<th>{col}</th>'
            table_html += '</tr></thead>'
            
            # Body
            table_html += '<tbody>'
            for idx, row in enumerate(display_rows, 1):
                table_html += '<tr>'
                table_html += f'<td style="color: #9ca3af; font-size: 12px;">{idx}</td>'
                for col in columns:
                    cell_value = row.get(col, "")
                    # Sayı formatla
                    if isinstance(cell_value, (int, float)):
                        if "cost" in col.lower() or "maliyet" in col.lower() or "tutar" in col.lower():
                            cell_value = f"₺{cell_value:,.2f}"
                        elif isinstance(cell_value, float):
                            cell_value = f"{cell_value:,.2f}"
                        else:
                            cell_value = f"{cell_value:,}"
                    table_html += f'<td>{cell_value}</td>'
                table_html += '</tr>'
            table_html += '</tbody></table>'
            
            content += f"""
    <div class="section">
        <div class="section-title">📋 {table_title}</div>
        {f'<p style="color: #6b7280; font-size: 13px; margin-bottom: 12px;">{table_desc}</p>' if table_desc else ''}
        {table_html}
        <p style="color: #9ca3af; font-size: 12px; text-align: right; margin-top: 8px;">
            Gösterilen: {showing} / Toplam: {total} kayıt
        </p>
    </div>
            """
    
    # =========================================================================
    # 7. FOOTER
    # =========================================================================
    content += """
    <div class="footer">
        <p>Bu email <strong>Promptever RAG</strong> sistemi tarafından otomatik olarak oluşturulmuştur.</p>
        <p style="margin-top: 8px;">© 2024 Promptever - Kurumsal Deneyim Mimarisi</p>
    </div>
    """
    
    return EMAIL_TEMPLATE.format(content=content)


def generate_alert_email_html(
    alert_name: str,
    query_text: str,
    metric_path: str,
    old_value: Any,
    new_value: Any,
    change_pct: float = 0,
) -> str:
    """Alert bildirimi için HTML email oluştur"""
    
    alert_class = "alert-change"
    change_icon = "🔔"
    
    if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
        if new_value > old_value:
            alert_class = "alert-increase"
            change_icon = "📈"
        elif new_value < old_value:
            alert_class = "alert-decrease"
            change_icon = "📉"
    
    change_text = f"{'+' if change_pct > 0 else ''}{change_pct:.1f}%" if change_pct != 0 else "Değişim var"
    
    content = f"""
    <div class="header">
        <h1>{change_icon} Alert: {alert_name}</h1>
        <div class="meta">
            <strong>Tarih:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </div>
    </div>
    
    <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
        <h3 style="margin: 0 0 10px 0; color: #92400e;">Değişiklik Tespit Edildi</h3>
        <p style="margin: 5px 0;"><strong>Metrik:</strong> {metric_path}</p>
        <p style="margin: 5px 0;"><strong>Önceki Değer:</strong> {old_value}</p>
        <p style="margin: 5px 0;"><strong>Yeni Değer:</strong> {new_value}</p>
        <p style="margin: 5px 0;"><strong>Değişim:</strong> {change_text}</p>
    </div>
    
    <div class="section">
        <div class="section-title">🔍 Sorgu</div>
        <div class="query-box">{query_text}</div>
    </div>
    
    <div class="footer">
        <p>Bu alert <strong>Promptever Monitoring</strong> sistemi tarafından gönderilmiştir.</p>
    </div>
    """
    
    return EMAIL_TEMPLATE.format(content=content)


# ============================================================================
# N8N WEBHOOK INTEGRATION
# ============================================================================

async def send_via_n8n_webhook(
    to_email: str,
    subject: str,
    html_content: str,
    from_name: str = "Promptever",
) -> Dict[str, Any]:
    """
    Mevcut n8n workflow'unu çağır.
    """
    payload = {
        "email": to_email,
        "subject": subject,
        "html": html_content,
        "name": from_name,
        "timestamp": datetime.now().isoformat(),
        "source": "promptever-rag",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                N8N_EMAIL_WEBHOOK,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            logger.info(f"n8n webhook response: {response.status_code}")
            
            if response.status_code == 200:
                return {"success": True, "data": response.json() if response.text else {}}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
    except Exception as e:
        logger.error(f"n8n webhook hatası: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MAIN SERVICE CLASS
# ============================================================================

class EmailService:
    """Email Service - mevcut n8n workflow'u üzerinden email gönderir"""
    
    @staticmethod
    async def send_instant_email(
        recipients: List[str],
        query_text: str,
        chat_response: Dict[str, Any],
        subject: Optional[str] = None,
        include_tables: bool = True,
        include_llm_answer: bool = True,
        include_statistics: bool = True,
        user_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Chat sonucunu anlık olarak email gönder"""
        
        # Subject oluştur
        if not subject:
            intent = chat_response.get("intent", "sorgu")
            subject = f"📊 Promptever Rapor: {intent[:50]}"
        
        # HTML içerik oluştur
        html_content = generate_chat_email_html(
            query_text=query_text,
            chat_response=chat_response,
            include_tables=include_tables,
            include_llm_answer=include_llm_answer,
            include_statistics=include_statistics,
            user_note=user_note,
        )
        
        # Her alıcıya gönder
        sent_to = []
        errors = []
        
        for recipient in recipients:
            result = await send_via_n8n_webhook(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
            )
            
            if result["success"]:
                sent_to.append(recipient)
            else:
                errors.append(f"{recipient}: {result.get('error')}")
        
        # Log kaydet (MongoDB varsa)
        if HAS_MONGO:
            try:
                logs_collection.insert_one({
                    "_id": ObjectId(),
                    "type": "instant",
                    "query_text": query_text,
                    "recipients": recipients,
                    "subject": subject,
                    "sent_at": datetime.now(),
                    "status": "sent" if sent_to else "failed",
                    "sent_to": sent_to,
                    "errors": errors,
                    "user_note": user_note,
                    "response_summary": {
                        "intent": chat_response.get("intent"),
                        "table_count": len(chat_response.get("tables", [])),
                    },
                })
            except Exception as e:
                logger.warning(f"Log kaydedilemedi: {e}")
        
        return {
            "success": len(sent_to) > 0,
            "message": f"{len(sent_to)} email gönderildi" if sent_to else f"Hata: {'; '.join(errors)}",
            "sent_to": sent_to,
            "errors": errors,
        }
    
    @staticmethod
    async def send_alert_email(
        recipients: List[str],
        alert_name: str,
        query_text: str,
        metric_path: str,
        old_value: Any,
        new_value: Any,
        change_pct: float = 0,
    ) -> Dict[str, Any]:
        """Alert bildirimi gönder"""
        
        subject = f"🔔 Alert: {alert_name}"
        
        html_content = generate_alert_email_html(
            alert_name=alert_name,
            query_text=query_text,
            metric_path=metric_path,
            old_value=old_value,
            new_value=new_value,
            change_pct=change_pct,
        )
        
        sent_to = []
        for recipient in recipients:
            result = await send_via_n8n_webhook(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
            )
            if result["success"]:
                sent_to.append(recipient)
        
        return {
            "success": len(sent_to) > 0,
            "sent_to": sent_to,
        }
    
    @staticmethod
    def preview_email_html(
        query_text: str,
        chat_response: Dict[str, Any],
        include_tables: bool = True,
        include_llm_answer: bool = True,
        include_statistics: bool = True,
        user_note: Optional[str] = None,
    ) -> str:
        """Email HTML önizlemesi döndür"""
        return generate_chat_email_html(
            query_text=query_text,
            chat_response=chat_response,
            include_tables=include_tables,
            include_llm_answer=include_llm_answer,
            include_statistics=include_statistics,
            user_note=user_note,
        )


# Singleton
email_service = EmailService()
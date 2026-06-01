import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


ALERT_TEMPLATE = """
<html>
<body style="font-family:sans-serif;max-width:520px;margin:40px auto;color:#222">
  <h2 style="color:#1a1a1a">✈ Price drop on {origin} → {destination}</h2>
  <p style="font-size:32px;font-weight:700;color:#16a34a;margin:8px 0">${trigger_price}</p>
  <p style="color:#555;margin-top:0">Down {pct_change:.0f}% from the 30-day average of ${baseline_price:.0f}</p>
  <hr style="border:.5px solid #e5e5e5;margin:24px 0">
  <p style="font-size:14px;color:#777">This is an automated price alert from Flight Tracker.</p>
  <a href="{frontend_url}/route/{origin}/{destination}"
     style="display:inline-block;margin-top:12px;padding:10px 20px;
            background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;font-size:14px">
    View price history →
  </a>
</body>
</html>
"""


async def send_price_alert(
    to_email: str,
    origin: str,
    destination: str,
    trigger_price: float,
    baseline_price: float,
    pct_change: float,
):
    if not settings.sendgrid_api_key:
        logger.warning("SENDGRID_API_KEY not set — skipping email")
        return False

    html = ALERT_TEMPLATE.format(
        origin=origin,
        destination=destination,
        trigger_price=trigger_price,
        baseline_price=baseline_price,
        pct_change=abs(pct_change),
        frontend_url=settings.frontend_url,
    )

    message = Mail(
        from_email=settings.alert_from_email,
        to_emails=to_email,
        subject=f"✈ Price drop: {origin}→{destination} now ${trigger_price:.0f}",
        html_content=html,
    )

    try:
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        logger.info(f"Alert sent to {to_email} — status {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False

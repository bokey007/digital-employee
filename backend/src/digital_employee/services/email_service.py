"""Email service — SMTP sending only. Inbound email is replaced by the web portal."""

from __future__ import annotations

import email.utils
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from digital_employee.settings import Settings

logger = structlog.get_logger(__name__)

# ── CTA button template ──────────────────────────────────────────────────────

_CTA_BUTTON_HTML = """
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 24px 0;">
  <tr>
    <td align="center">
      <a href="{url}"
         style="display:inline-block; background-color:#08312A; color:#00E47C;
                font-family:Calibri,sans-serif; font-size:15px; font-weight:bold;
                text-decoration:none; padding:14px 32px; border-radius:6px;
                letter-spacing:0.5px;">
        {label}
      </a>
    </td>
  </tr>
  <tr>
    <td align="center" style="padding-top:10px;">
      <p style="font-family:Calibri,sans-serif; font-size:11px; color:#888; margin:0;">
        Or copy this link: <a href="{url}" style="color:#08312A;">{url}</a>
      </p>
    </td>
  </tr>
</table>
"""


def _cta_button(url: str, label: str = "Open Portal →") -> str:
    return _CTA_BUTTON_HTML.format(url=url, label=label)


class EmailService:
    """Handles outbound email operations via SMTP."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── SMTP ─────────────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        body_html: str,
        body_text: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> None:
        """Send an email via SMTP."""
        recipients = [to] if isinstance(to, str) else to

        msg = MIMEMultipart("alternative")
        msg["From"] = self._settings.email_address
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Message-ID"] = email.utils.make_msgid(
            domain=self._settings.email_address.split("@")[-1]
        )

        if reply_to_message_id:
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            if self._settings.email_use_tls:
                with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(self._settings.email_address, self._settings.email_password)
                    server.sendmail(self._settings.email_address, recipients, msg.as_string())
            else:
                with smtplib.SMTP_SSL(
                    self._settings.smtp_host,
                    self._settings.smtp_port,
                    context=ssl.create_default_context(),
                ) as server:
                    server.login(self._settings.email_address, self._settings.email_password)
                    server.sendmail(self._settings.email_address, recipients, msg.as_string())

            logger.info("email_sent", to=recipients, subject=subject)
        except Exception as exc:
            logger.error("email_send_failed", to=recipients, subject=subject, error=str(exc))
            raise

    # ── Workflow notification emails ──────────────────────────────────────────

    def send_update_request(
        self,
        lead_email: str,
        lead_name: str,
        programme: str,
        workstream: str,
        edition_title: str,
        portal_url: str,
    ) -> None:
        """Send a content submission request to a workstream lead with a portal link."""
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"Action Required: Submit Your Updates — {programme} / {workstream}"
        )

        is_quality = (
            programme.lower() == "quality" or workstream.lower() == "quality metrics"
        )

        if is_quality:
            guidance = """
            <ul style="font-family:Calibri,sans-serif; color:#333; font-size:14px; line-height:1.8;">
              <li><strong>Lean Projects Completed</strong></li>
              <li><strong>GB Projects Completed</strong></li>
              <li><strong>Lean Trained &amp; Tested</strong> (%)</li>
              <li><strong>GB Trained &amp; Tested</strong> (%)</li>
              <li><strong>Lean Certified</strong> (%)</li>
              <li><strong>GB Certified</strong> (%)</li>
            </ul>"""
        else:
            guidance = """
            <ul style="font-family:Calibri,sans-serif; color:#333; font-size:14px; line-height:1.8;">
              <li><strong>Key Highlights</strong></li>
              <li><strong>Delivery Updates</strong></li>
              <li><strong>Innovation &amp; Value Add</strong></li>
            </ul>"""

        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:600px; margin:auto;">
          <div style="background:#08312A; padding:20px 32px; border-radius:8px 8px 0 0;">
            <h2 style="color:#00E47C; margin:0; font-size:20px;">📋 Newsletter Update Request</h2>
            <p style="color:#fff; margin:4px 0 0; font-size:13px;">Boehringer Ingelheim — Digital Employee</p>
          </div>
          <div style="background:#fff; padding:28px 32px; border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Hi <strong>{lead_name.split()[0]}</strong>,</p>
            <p style="font-size:14px; color:#444;">
              We are preparing the <strong>{edition_title}</strong> and need your updates for
              <strong>{programme} — {workstream}</strong>.
            </p>
            <p style="font-size:14px; color:#444;">Please cover the following areas:</p>
            {guidance}
            <p style="font-size:14px; color:#444;">
              Click the button below to open your personalised submission portal.
              The AI will professionally reword your bullet points and you can review,
              refine, and approve them — all in one place. <strong>No email reply needed.</strong>
            </p>
            {_cta_button(portal_url, "Submit My Updates →")}
            <hr style="border:none; border-top:1px solid #e5e7eb; margin:24px 0;"/>
            <p style="font-size:12px; color:#999;">
              This link is personal to you and expires in {self._settings.portal_token_ttl_days} days.
              If you have any questions, reply to this email.
            </p>
          </div>
        </body></html>
        """
        self.send_email(lead_email, subject, body_html)

    def send_programme_section_for_review(
        self,
        programme_lead_email: str,
        programme_lead_name: str,
        programme: str,
        section_html: str,
        edition_title: str,
        portal_url: str,
    ) -> None:
        """Send the consolidated programme section to the programme lead for portal review."""
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"{edition_title} — {programme} Section: Awaiting Your Review"
        )
        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:700px; margin:auto;">
          <div style="background:#08312A; padding:20px 32px; border-radius:8px 8px 0 0;">
            <h2 style="color:#00E47C; margin:0; font-size:20px;">👁️ Programme Section Review</h2>
            <p style="color:#fff; margin:4px 0 0; font-size:13px;">Boehringer Ingelheim — Digital Employee</p>
          </div>
          <div style="background:#fff; padding:28px 32px; border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Hi <strong>{programme_lead_name.split()[0]}</strong>,</p>
            <p style="font-size:14px; color:#444;">
              All workstream leads in <strong>{programme}</strong> have submitted and approved their
              contributions. The consolidated section for <strong>{edition_title}</strong> is ready
              for your review.
            </p>
            <p style="font-size:14px; color:#444;">
              Click the button below to open the review portal where you can read the section,
              chat with the AI to request any refinements, and approve.
            </p>
            {_cta_button(portal_url, "Review &amp; Approve →")}
            <p style="font-size:12px; color:#999;">
              This link expires in {self._settings.portal_token_ttl_days} days.
            </p>
          </div>
        </body></html>
        """
        self.send_email(programme_lead_email, subject, body_html)

    def send_newsletter_for_review(
        self,
        reviewer_email: str,
        reviewer_name: str,
        newsletter_html: str,
        edition_title: str,
        portal_url: str,
    ) -> None:
        """Send the consolidated newsletter to Ashwin or Anuj for review via the portal."""
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"{edition_title} — For Your Review & Approval"
        )
        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:700px; margin:auto;">
          <div style="background:#08312A; padding:20px 32px; border-radius:8px 8px 0 0;">
            <h2 style="color:#00E47C; margin:0; font-size:20px;">✅ Newsletter Ready for Review</h2>
            <p style="color:#fff; margin:4px 0 0; font-size:13px;">Boehringer Ingelheim — Digital Employee</p>
          </div>
          <div style="background:#fff; padding:28px 32px; border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Hi <strong>{reviewer_name.split()[0]}</strong>,</p>
            <p style="font-size:14px; color:#444;">
              The <strong>{edition_title}</strong> is ready for your review. All workstream leads
              have approved their sections.
            </p>
            <p style="font-size:14px; color:#444;">
              Click the button below to open the review portal where you can read the full newsletter,
              ask the AI to refine any section, and approve or send feedback.
            </p>
            {_cta_button(portal_url, "Review Full Newsletter →")}
            <p style="font-size:12px; color:#999;">
              This link expires in {self._settings.portal_token_ttl_days} days.
            </p>
          </div>
        </body></html>
        """
        self.send_email(reviewer_email, subject, body_html)

    def send_reminder(
        self,
        lead_email: str,
        lead_name: str,
        programme: str,
        workstream: str,
        edition_title: str,
        reminder_number: int,
        portal_url: str,
    ) -> None:
        """Send a follow-up reminder with a fresh portal link."""
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"Reminder #{reminder_number} — {programme} / {workstream}"
        )
        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:600px; margin:auto;">
          <div style="background:#08312A; padding:20px 32px; border-radius:8px 8px 0 0;">
            <h2 style="color:#00E47C; margin:0; font-size:20px;">🔔 Reminder #{reminder_number}</h2>
            <p style="color:#fff; margin:4px 0 0; font-size:13px;">Boehringer Ingelheim — Digital Employee</p>
          </div>
          <div style="background:#fff; padding:28px 32px; border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Hi <strong>{lead_name.split()[0]}</strong>,</p>
            <p style="font-size:14px; color:#444;">
              This is a gentle reminder — we are still awaiting your newsletter updates for
              <strong>{programme} — {workstream}</strong> in the <strong>{edition_title}</strong>.
            </p>
            <p style="font-size:14px; color:#444;">
              Your submission portal is still open. It takes just a few minutes!
            </p>
            {_cta_button(portal_url, "Submit My Updates →")}
            <p style="font-size:12px; color:#999;">
              This is a new link — it expires in {self._settings.portal_token_ttl_days} days.
            </p>
          </div>
        </body></html>
        """
        self.send_email(lead_email, subject, body_html)

    def send_reviewer_reminder(
        self,
        reviewer_email: str,
        reviewer_name: str,
        role_label: str,
        edition_title: str,
        reminder_number: int,
        portal_url: str,
    ) -> None:
        """Send a follow-up reminder to a reviewer (programme lead, Ashwin, or Anuj)."""
        first_name = reviewer_name.split()[0]
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"Reminder #{reminder_number} — Action Required: {edition_title}"
        )
        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:600px; margin:auto;">
          <div style="background:#08312A; padding:20px 32px; border-radius:8px 8px 0 0;">
            <h2 style="color:#00E47C; margin:0; font-size:20px;">🔔 Reminder #{reminder_number}</h2>
            <p style="color:#fff; margin:4px 0 0; font-size:13px;">Boehringer Ingelheim — Digital Employee</p>
          </div>
          <div style="background:#fff; padding:28px 32px; border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Hi <strong>{first_name}</strong>,</p>
            <p style="font-size:14px; color:#444;">
              This is a gentle reminder — your review and approval of the
              <strong>{edition_title}</strong> is still pending as <strong>{role_label}</strong>.
            </p>
            <p style="font-size:14px; color:#444;">
              Please use the button below to open your review portal and approve or request changes.
            </p>
            {_cta_button(portal_url, "Open Review Portal →")}
            <p style="font-size:12px; color:#999;">
              This is a new link — it expires in {self._settings.portal_token_ttl_days} days.
            </p>
          </div>
        </body></html>
        """
        self.send_email(reviewer_email, subject, body_html)

    def send_newsletter_to_client(
        self,
        distribution_list: list[str],
        newsletter_html: str,
        edition_title: str,
    ) -> None:
        """Send the final approved newsletter to the distribution list."""
        subject = f"{self._settings.newsletter_subject_prefix} {edition_title}"
        self.send_email(distribution_list, subject, newsletter_html)

    def send_skip_notification(
        self,
        reviewer_email: str,
        reviewer_name: str,
        edition_title: str,
        skipped_leads: list[dict],
        all_lead_emails: list[str],
    ) -> None:
        """Notify the delivery leader about workstreams skipped due to non-response."""
        subject = (
            f"{self._settings.newsletter_subject_prefix} "
            f"{edition_title} — Skipped Workstreams"
        )
        skipped_rows = "".join(
            f"""<tr>
                <td style="padding:8px;border:1px solid #e5e7eb;">{s['programme']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{s['workstream']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{s['lead_name']} ({s['lead_email']})</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{s['reminder_count']} reminders</td>
            </tr>"""
            for s in skipped_leads
        )
        body_html = f"""
        <html><body style="font-family:Calibri,sans-serif; max-width:700px; margin:auto;">
          <p>Hi {reviewer_name},</p>
          <p>While preparing <strong>{edition_title}</strong>, the following leads did not respond.
          Their sections have been <strong>excluded</strong>:</p>
          <table style="border-collapse:collapse;width:100%;margin:16px 0;">
            <thead><tr style="background:#f9fafb;">
              <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Programme</th>
              <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Workstream</th>
              <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Lead</th>
              <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Attempts</th>
            </tr></thead>
            <tbody>{skipped_rows}</tbody>
          </table>
          <p>The newsletter will proceed with available approved content.</p>
          <p>Thank you,<br/>{self._settings.app_name}</p>
        </body></html>
        """
        recipients = [reviewer_email] + [e for e in all_lead_emails if e != reviewer_email]
        self.send_email(recipients, subject, body_html)

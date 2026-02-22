"""Email service — IMAP reading and SMTP sending."""

from __future__ import annotations

import email
import email.utils
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import imapclient
import structlog

from digital_employee.settings import Settings

logger = structlog.get_logger(__name__)


@dataclass
class IncomingEmail:
    """Parsed representation of an incoming email."""

    uid: int
    from_addr: str
    from_name: str
    to_addr: str
    subject: str
    body_text: str
    body_html: str
    date: str
    message_id: str
    in_reply_to: str | None = None
    references: str | None = None
    headers: dict = field(default_factory=dict)


class EmailService:
    """Handles all email operations: reading via IMAP and sending via SMTP."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._imap: Optional[imapclient.IMAPClient] = None

    # ── IMAP ─────────────────────────────────────────────────────────────────

    def connect_imap(self) -> imapclient.IMAPClient:
        """Establish a connection to the IMAP server."""
        ctx = ssl.create_default_context()
        self._imap = imapclient.IMAPClient(
            self._settings.imap_host,
            port=self._settings.imap_port,
            ssl=True,
            ssl_context=ctx,
        )
        self._imap.login(self._settings.email_address, self._settings.email_password)
        logger.info("imap_connected", host=self._settings.imap_host)
        return self._imap

    def disconnect_imap(self) -> None:
        """Cleanly close the IMAP connection."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def fetch_unread_emails(self, folder: str = "INBOX", max_emails: int = 20) -> list[IncomingEmail]:
        """Fetch recent unread emails from the inbox.

        Filters by UNSEEN + last 7 days. Caps at max_emails to control costs.
        No subject filtering — every email gets processed by the LLM brain.
        """
        from datetime import datetime, timedelta

        if not self._imap:
            self.connect_imap()

        assert self._imap is not None
        self._imap.select_folder(folder)

        # Fetch unread emails from the last 7 days that match our prefix
        since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        
        # We start with the base criteria: unread and since last 7 days
        criteria = ["UNSEEN", "SINCE", since_date]
        
        # Add subject prefix filter - this is crucial when there are 100k+ unread emails
        if self._settings.newsletter_subject_prefix:
            criteria.extend(["SUBJECT", self._settings.newsletter_subject_prefix])
            
        uids = self._imap.search(criteria)

        if not uids:
            # Fallback: if no recent unread matches prefix, look for any UNSEEN from last 7 days 
            # to handle edge cases where prefix varies, but limit heavily.
            criteria = ["UNSEEN", "SINCE", since_date]
            uids = self._imap.search(criteria)
            if not uids:
                return []

        # Cap to avoid processing too many at once
        uids = uids[-max_emails:]

        logger.info("fetching_unread", count=len(uids))
        raw_messages = self._imap.fetch(uids, ["RFC822", "FLAGS"])

        results: list[IncomingEmail] = []
        for uid, data in raw_messages.items():
            try:
                parsed = self._parse_email(uid, data[b"RFC822"])
                results.append(parsed)
            except Exception as exc:
                logger.error("email_parse_error", uid=uid, error=str(exc))

        return results

    def mark_as_read(self, uid: int) -> None:
        """Mark a specific email as read."""
        if self._imap:
            self._imap.set_flags([uid], [imapclient.SEEN])

    def _parse_email(self, uid: int, raw: bytes) -> IncomingEmail:
        """Parse raw email bytes into an IncomingEmail object."""
        msg = email.message_from_bytes(raw)

        from_name, from_addr = email.utils.parseaddr(msg.get("From", ""))
        to_name, to_addr = email.utils.parseaddr(msg.get("To", ""))

        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if part.get("Content-Disposition") == "attachment":
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")

                if content_type == "text/plain":
                    body_text = decoded
                elif content_type == "text/html":
                    body_html = decoded
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = decoded
                else:
                    body_text = decoded

        return IncomingEmail(
            uid=uid,
            from_addr=from_addr,
            from_name=from_name,
            to_addr=to_addr,
            subject=msg.get("Subject", ""),
            body_text=body_text,
            body_html=body_html,
            date=msg.get("Date", ""),
            message_id=msg.get("Message-ID", ""),
            in_reply_to=msg.get("In-Reply-To"),
            references=msg.get("References"),
        )

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
        msg["Message-ID"] = email.utils.make_msgid(domain=self._settings.email_address.split("@")[-1])

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

    # ── Convenience methods ──────────────────────────────────────────────────

    def send_update_request(
        self,
        lead_email: str,
        lead_name: str,
        programme: str,
        workstream: str,
        edition_title: str,
    ) -> None:
        """Send a request for updates to a sub-workstream lead."""
        subject = f"{self._settings.newsletter_subject_prefix} Request for Updates — {programme} / {workstream}"
        
        if programme.lower() == "quality" or workstream.lower() == "quality metrics":
            body_html = f"""
            <html><body>
            <p>Hi {lead_name},</p>
            <p>We are preparing the <strong>{edition_title}</strong>.</p>
            <p>Could you please share the latest numbers for the <strong>Quality Dashboard</strong>
            covering the following metrics:</p>
            <ul>
                <li><strong>Lean Projects Completed</strong></li>
                <li><strong>GB Projects Completed</strong></li>
                <li><strong>Lean Trained &amp; Tested</strong> (%)</li>
                <li><strong>GB Trained &amp; Tested</strong> (%)</li>
                <li><strong>Lean Certified</strong> (%)</li>
                <li><strong>GB Certified</strong> (%)</li>
            </ul>
            <p>Please reply to this email with your updates at your earliest convenience.</p>
            <p>Thank you,<br/>{self._settings.app_name}</p>
            </body></html>
            """
        else:
            body_html = f"""
            <html><body>
            <p>Hi {lead_name},</p>
            <p>We are preparing the <strong>{edition_title}</strong>.</p>
            <p>Could you please share your updates for <strong>{programme} — {workstream}</strong>
            covering the following areas:</p>
            <ul>
                <li><strong>Key Highlights</strong></li>
                <li><strong>Delivery Updates</strong></li>
                <li><strong>Innovation &amp; Value Add</strong></li>
            </ul>
            <p>Please reply to this email with your updates at your earliest convenience.</p>
            <p>Thank you,<br/>{self._settings.app_name}</p>
            </body></html>
            """
        self.send_email(lead_email, subject, body_html)

    def send_approval_request(
        self,
        lead_email: str,
        lead_name: str,
        programme: str,
        workstream: str,
        reworded_content: str,
    ) -> None:
        """Send reworded content to a lead for approval."""
        subject = f"{self._settings.newsletter_subject_prefix} Review Your Section — {programme} / {workstream}"
        body_html = f"""
        <html><body>
        <p>Hi {lead_name},</p>
        <p>Thank you for your inputs. Below is the professionally reworded version of
        your section for <strong>{programme} — {workstream}</strong>:</p>
        <hr/>
        {reworded_content}
        <hr/>
        <p>Please reply with <strong>"Approved"</strong> if this looks good, or share
        any changes you'd like made.</p>
        <p>Thank you,<br/>{self._settings.app_name}</p>
        </body></html>
        """
        self.send_email(lead_email, subject, body_html)

    def send_newsletter_for_review(
        self,
        reviewer_email: str,
        reviewer_name: str,
        newsletter_html: str,
        edition_title: str,
    ) -> None:
        """Send the consolidated newsletter to the delivery leader for review.

        The newsletter content is embedded as rendered HTML so it's both
        readable and editable. Instructions are embedded inline by the template.
        """
        subject = f"{self._settings.newsletter_subject_prefix} {edition_title} — For Your Review"
        self.send_email(reviewer_email, subject, newsletter_html)

    def send_newsletter_to_client(
        self,
        distribution_list: list[str],
        newsletter_html: str,
        edition_title: str,
    ) -> None:
        """Send the final approved newsletter to the distribution list (clients, stakeholders, leaders)."""
        subject = f"{self._settings.newsletter_subject_prefix} {edition_title}"
        self.send_email(distribution_list, subject, newsletter_html)

    def send_reminder(
        self,
        lead_email: str,
        lead_name: str,
        programme: str,
        workstream: str,
        edition_title: str,
        reminder_number: int,
    ) -> None:
        """Send a follow-up reminder to a non-responsive lead."""
        subject = f"{self._settings.newsletter_subject_prefix} Reminder #{reminder_number} — {programme} / {workstream}"
        body_html = f"""
        <html><body>
        <p>Hi {lead_name},</p>
        <p>This is a gentle reminder regarding the <strong>{edition_title}</strong>.</p>
        <p>We are still awaiting your updates for <strong>{programme} — {workstream}</strong>.</p>
        <p>Could you please share your inputs covering:</p>
        <ol>
            <li><strong>Key Highlights</strong></li>
            <li><strong>Delivery Updates</strong></li>
            <li><strong>Innovation &amp; Value Add</strong></li>
        </ol>
        <p>Thank you,<br/>{self._settings.app_name}</p>
        </body></html>
        """
        self.send_email(lead_email, subject, body_html)

    def send_skip_notification(
        self,
        reviewer_email: str,
        reviewer_name: str,
        edition_title: str,
        skipped_leads: list[dict],
        all_lead_emails: list[str],
    ) -> None:
        """Notify the delivery leader about skipped workstreams due to unresponsive leads.

        CC all leads for transparency.

        Args:
            skipped_leads: list of dicts with keys: lead_name, lead_email, programme, workstream, reminder_count
        """
        subject = f"{self._settings.newsletter_subject_prefix} {edition_title} — Skipped Workstreams"

        skipped_rows = ""
        for s in skipped_leads:
            skipped_rows += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s['programme']}</td>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s['workstream']}</td>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s['lead_name']} ({s['lead_email']})</td>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s['reminder_count']} reminders sent</td>
            </tr>"""

        body_html = f"""
        <html><body>
        <p>Hi {reviewer_name},</p>
        <p>While preparing the <strong>{edition_title}</strong>, the following workstream leads
        did not respond despite multiple reminders. Their sections have been
        <strong>excluded</strong> from this edition:</p>
        <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
            <thead>
                <tr style="background: #f9fafb;">
                    <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Programme</th>
                    <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Workstream</th>
                    <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Lead</th>
                    <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Attempts</th>
                </tr>
            </thead>
            <tbody>{skipped_rows}</tbody>
        </table>
        <p>The newsletter will proceed with the available approved content.
        Please review and approve once the consolidated version is ready.</p>
        <p>Thank you,<br/>{self._settings.app_name}</p>
        </body></html>
        """
        # Send to reviewer, CC all leads
        recipients = [reviewer_email] + [e for e in all_lead_emails if e != reviewer_email]
        self.send_email(recipients, subject, body_html)


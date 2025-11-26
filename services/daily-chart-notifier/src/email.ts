import nodemailer from "nodemailer";
import type { Config, Attachment } from "./types";
import { logger } from "./utils/logger";
import {
  formatForEmailSubject,
  formatForLogTimestamp,
  bangkokNow,
} from "./utils/time";

export function buildEmailHtml(date: Date, timezone: string): string {
  const formattedDate = formatForLogTimestamp(date, timezone);

  return `
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .header { background-color: #2563eb; color: white; padding: 20px; }
    .content { padding: 20px; }
    .footer { background-color: #f3f4f6; padding: 15px; font-size: 12px; color: #666; }
    h1 { margin: 0; font-size: 24px; }
    ul { margin: 10px 0; padding-left: 20px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Munbon Daily Report</h1>
  </div>
  <div class="content">
    <p>Report generated: <strong>${formattedDate}</strong></p>
    <p>Timezone: ${timezone}</p>

    <h3>Attachments:</h3>
    <ul>
      <li><strong>Moisture Dashboard</strong> - Screenshot of moisture sensor monitoring</li>
      <li><strong>Water Level Dashboard</strong> - Screenshot of water level monitoring</li>
      <li><strong>PM2 Logs</strong> - Last 24 hours of moisture sensor service logs</li>
    </ul>

    <p>This is an automated daily report from the Munbon Irrigation System.</p>
  </div>
  <div class="footer">
    <p>Munbon Irrigation Control System - Automated Report</p>
  </div>
</body>
</html>
`.trim();
}

export async function sendEmail(
  config: Config,
  attachments: Attachment[],
): Promise<void> {
  const transporter = nodemailer.createTransport({
    host: config.smtp.host,
    port: config.smtp.port,
    secure: config.smtp.port === 465,
    auth: {
      user: config.smtp.user,
      pass: config.smtp.pass,
    },
  });

  const now = bangkokNow(config.timezone);
  const subject = `Munbon Daily Report - ${formatForEmailSubject(now, config.timezone)}`;
  const html = buildEmailHtml(now, config.timezone);

  const mailOptions = {
    from: config.smtp.from,
    to: config.email.to,
    subject,
    html,
    attachments: attachments.map((att) => ({
      filename: att.filename,
      ...(att.path ? { path: att.path } : {}),
      ...(att.content ? { content: att.content } : {}),
    })),
  };

  logger.info({ to: config.email.to, subject }, "Sending email");

  const result = await transporter.sendMail(mailOptions);

  logger.info({ messageId: result.messageId }, "Email sent successfully");
}

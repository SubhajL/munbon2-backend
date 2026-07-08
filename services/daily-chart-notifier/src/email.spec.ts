import { describe, expect, test, vi, beforeEach } from "vitest";
import { sendEmail, buildEmailHtml } from "./email";
import type { Config, Attachment } from "./types";

let mockSendMail: ReturnType<typeof vi.fn>;
let mockCreateTransport: ReturnType<typeof vi.fn>;

vi.mock("nodemailer", () => {
  const sendMail = vi.fn().mockResolvedValue({ messageId: "test-123" });
  const createTransport = vi.fn(() => ({ sendMail }));

  return {
    default: { createTransport },
    createTransport,
    __getMocks: () => ({ sendMail, createTransport }),
  };
});

const mockConfig: Config = {
  smtp: {
    host: "smtp.gmail.com",
    port: 587,
    user: "sender@example.com",
    pass: "app-password",
    from: "Munbon Daily Report <sender@example.com>",
  },
  email: { to: "recipient@example.com" },
  ssh: {
    host: "192.168.1.1",
    port: 22,
    user: "ubuntu",
    keyPath: "/path/to/key.pem",
  },
  dashboards: {
    moistureUrl: "http://localhost:8080/moisture.html",
    waterLevelUrl: "http://localhost:8080/water.html",
  },
  pm2LogPath: "~/.pm2/logs/app-out.log",
  timezone: "Asia/Bangkok",
};

describe("buildEmailHtml", () => {
  test("includes report date in HTML", () => {
    const date = new Date("2024-01-15T13:00:00Z");

    const html = buildEmailHtml(date, "Asia/Bangkok");

    expect(html).toContain("2024-01-15");
  });

  test("includes timezone information", () => {
    const date = new Date("2024-01-15T13:00:00Z");

    const html = buildEmailHtml(date, "Asia/Bangkok");

    expect(html).toContain("Asia/Bangkok");
  });

  test("includes attachment description", () => {
    const date = new Date("2024-01-15T13:00:00Z");

    const html = buildEmailHtml(date, "Asia/Bangkok");

    expect(html).toContain("Moisture");
    expect(html).toContain("Water Level");
    expect(html).toContain("PM2");
  });
});

describe("sendEmail", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const nodemailer = await import("nodemailer");
    const mocks = (nodemailer as any).__getMocks();
    mockSendMail = mocks.sendMail;
    mockCreateTransport = mocks.createTransport;
  });

  test("creates transporter with Gmail SMTP settings", async () => {
    const attachments: Attachment[] = [];

    await sendEmail(mockConfig, attachments);

    expect(mockCreateTransport).toHaveBeenCalledWith({
      host: "smtp.gmail.com",
      port: 587,
      secure: false,
      auth: {
        user: "sender@example.com",
        pass: "app-password",
      },
    });
  });

  test("sends email to configured recipient", async () => {
    const attachments: Attachment[] = [];

    await sendEmail(mockConfig, attachments);

    expect(mockSendMail).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "recipient@example.com",
        from: "Munbon Daily Report <sender@example.com>",
      }),
    );
  });

  test("includes date in email subject", async () => {
    const attachments: Attachment[] = [];

    await sendEmail(mockConfig, attachments);

    expect(mockSendMail).toHaveBeenCalledWith(
      expect.objectContaining({
        subject: expect.stringMatching(
          /Munbon Daily Report - \d{4}-\d{2}-\d{2}/,
        ),
      }),
    );
  });

  test("attaches provided files", async () => {
    const attachments: Attachment[] = [
      { filename: "screenshot-1.png", path: "/tmp/screenshot-1.png" },
      { filename: "logs.txt", content: "Log content here" },
    ];

    await sendEmail(mockConfig, attachments);

    expect(mockSendMail).toHaveBeenCalledWith(
      expect.objectContaining({
        attachments: expect.arrayContaining([
          expect.objectContaining({ filename: "screenshot-1.png" }),
          expect.objectContaining({ filename: "logs.txt" }),
        ]),
      }),
    );
  });

  test("throws on SMTP failure", async () => {
    mockSendMail.mockRejectedValueOnce(new Error("SMTP connection failed"));
    const attachments: Attachment[] = [];

    await expect(sendEmail(mockConfig, attachments)).rejects.toThrow(
      "SMTP connection failed",
    );
  });
});

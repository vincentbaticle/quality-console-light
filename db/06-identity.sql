DROP DATABASE IF EXISTS identity;
CREATE DATABASE identity;

CREATE TABLE identity.users (
  id VARCHAR(40) PRIMARY KEY,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NULL,
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  blocked BOOLEAN NOT NULL DEFAULT FALSE,
  failed_logins INT NOT NULL DEFAULT 0,
  logins_count INT NOT NULL DEFAULT 0,
  totp_secret VARCHAR(64) NULL,
  totp_last_step BIGINT NULL,
  created_at DATETIME(3) NOT NULL,
  last_login DATETIME(3) NULL
);

CREATE TABLE identity.tickets (
  token VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(40) NOT NULL,
  kind ENUM('set_password', 'reset_password', 'unblock', 'mfa') NOT NULL,
  created_at DATETIME(3) NOT NULL,
  expires_at DATETIME(3) NOT NULL,
  used_at DATETIME(3) NULL,
  CONSTRAINT fk_tickets_user FOREIGN KEY (user_id) REFERENCES identity.users (id)
);

CREATE VIEW identity.accounts AS
  SELECT id, email, password_hash IS NOT NULL AS has_password, totp_secret IS NOT NULL AS has_totp, email_verified, blocked, failed_logins, logins_count, created_at, last_login
  FROM identity.users;

CREATE VIEW identity.password_links AS
  SELECT user_id, kind, created_at, expires_at, used_at
  FROM identity.tickets;

INSERT INTO identity.users (id, email, password_hash, email_verified, blocked, failed_logins, logins_count, created_at, last_login) VALUES
  ('auth0|5f1c0a7e2b4d6f8a9c0e1d23', 'qa-mailbox+ada@mycompany.test', 'pbkdf2_sha256$100000$a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1$19d30d79b537dfeaeb5f441b13c28fe4f8ec20e2fec59b7641d3692ed0a492e7', TRUE, FALSE, 0, 12, '2026-09-01 09:00:00', '2026-10-07 18:12:00'),
  ('auth0|6a2d1b8f3c5e7a9b0d1f2e34', 'qa-mailbox+grace@mycompany.test', 'pbkdf2_sha256$100000$b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2$6e1eadd8ceb9b996e823ce612098f59705bda65875af1c8c742873bc07ad7a08', TRUE, TRUE, 10, 3, '2026-09-03 10:30:00', '2026-09-20 08:00:00'),
  ('auth0|7b3e2c9a4d6f8b0c1e2a3f45', 'qa-mailbox+zoe@mycompany.test', NULL, FALSE, FALSE, 0, 0, '2026-10-06 14:00:00', NULL);

INSERT INTO identity.users (id, email, password_hash, email_verified, blocked, failed_logins, logins_count, totp_secret, created_at, last_login) VALUES
  ('auth0|8c4f3d0b5e7a9c1d2f3b4a56', 'qa-mailbox+lin@mycompany.test', 'pbkdf2_sha256$100000$c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3$28615032a38d7730bc25e98ae0aa99dbf20a1a8a7c322f62450efd6fb973e1fa', TRUE, FALSE, 0, 5, 'OF2WC3DJOR4S2Y3PNZZW63DFFV2G65DQ', '2026-09-10 11:00:00', '2026-10-08 09:30:00');

GRANT SELECT ON identity.accounts TO 'console_reader'@'%';
GRANT SELECT ON identity.password_links TO 'console_reader'@'%';

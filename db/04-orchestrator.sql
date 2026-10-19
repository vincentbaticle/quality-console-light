DROP DATABASE IF EXISTS orchestrator;
CREATE DATABASE orchestrator;

CREATE TABLE orchestrator.workflows (
  id CHAR(36) PRIMARY KEY,
  kind VARCHAR(40) NOT NULL,
  order_id INT NOT NULL,
  status ENUM('running', 'completed', 'failed') NOT NULL,
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL
);

CREATE TABLE orchestrator.workflow_steps (
  workflow_id CHAR(36) NOT NULL,
  position TINYINT NOT NULL,
  name VARCHAR(40) NOT NULL,
  status ENUM('pending', 'running', 'done', 'failed', 'skipped') NOT NULL,
  detail VARCHAR(255) NULL,
  finished_at DATETIME(3) NULL,
  PRIMARY KEY (workflow_id, position),
  CONSTRAINT fk_steps_workflow FOREIGN KEY (workflow_id) REFERENCES orchestrator.workflows (id)
);

GRANT SELECT, SHOW VIEW ON orchestrator.* TO 'console_reader'@'%';

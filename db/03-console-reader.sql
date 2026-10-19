CREATE USER IF NOT EXISTS 'console_reader'@'%' IDENTIFIED BY 'reader';
GRANT SELECT, SHOW VIEW ON mycompany.* TO 'console_reader'@'%';
GRANT SELECT ON performance_schema.table_io_waits_summary_by_table TO 'console_reader'@'%';

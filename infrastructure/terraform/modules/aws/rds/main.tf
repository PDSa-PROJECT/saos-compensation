resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-postgres"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name_prefix}-postgres-"
  description = "PostgreSQL access restricted to the configured IP WHITELIST."
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "whitelist" {
  for_each = var.ip_whitelist

  security_group_id = aws_security_group.this.id
  description       = "PostgreSQL IP WHITELIST"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name_prefix}-postgres-"
  family      = "postgres${split(".", var.settings.engine_version)[0]}"
  description = "PostgreSQL parameters enforcing encrypted client connections."

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  identifier                  = "${var.name_prefix}-postgres"
  engine                      = "postgres"
  engine_version              = var.settings.engine_version
  instance_class              = var.settings.instance_class
  allocated_storage           = var.settings.allocated_storage
  storage_type                = "gp3"
  storage_encrypted           = true
  max_allocated_storage       = 0
  db_name                     = var.settings.database_name
  username                    = var.settings.master_username
  manage_master_user_password = true
  port                        = 5432
  multi_az                    = false
  publicly_accessible         = true
  db_subnet_group_name        = aws_db_subnet_group.this.name
  vpc_security_group_ids      = [aws_security_group.this.id]
  parameter_group_name        = aws_db_parameter_group.this.name
  backup_retention_period     = 0
  deletion_protection         = var.settings.deletion_protection
  skip_final_snapshot         = var.settings.skip_final_snapshot
  final_snapshot_identifier   = var.settings.final_snapshot_identifier
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false
  copy_tags_to_snapshot       = true
}

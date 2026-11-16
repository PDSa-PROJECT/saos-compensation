output "identifier" {
  description = "Database identifier for manual start operations."
  value       = aws_db_instance.this.identifier
}

output "arn" {
  description = "Database ARN for narrowly scoped IAM permissions."
  value       = aws_db_instance.this.arn
}

output "address" {
  description = "Database DNS hostname; use this rather than its public IP."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "PostgreSQL connection port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "master_secret_arn" {
  description = "RDS-managed secret ARN; the password is never read by Terraform."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

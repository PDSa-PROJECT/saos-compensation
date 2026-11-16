output "vpc_id" {
  description = "Dedicated project VPC ID."
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnets spanning two availability zones for the RDS subnet group."
  value       = module.vpc.public_subnet_ids
}

output "rds" {
  description = "Database connection metadata and secret reference, never the password."
  value = {
    identifier        = module.rds.identifier
    address           = module.rds.address
    port              = module.rds.port
    database_name     = module.rds.database_name
    master_secret_arn = module.rds.master_secret_arn
  }
}

output "vpc_id" {
  description = "Dedicated project VPC ID."
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnets spanning two availability zones for the RDS subnet group."
  value       = module.vpc.public_subnet_ids
}

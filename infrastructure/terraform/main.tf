module "vpc" {
  source = "./modules/aws/vpc"

  providers = {
    aws = aws
  }

  name_prefix           = var.project_name
  cidr_block            = var.vpc_cidr
  public_subnet_newbits = var.public_subnet_newbits
}

module "rds" {
  source = "./modules/aws/rds"

  providers = {
    aws = aws
  }

  name_prefix  = var.project_name
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.public_subnet_ids
  ip_whitelist = var.rds_ip_whitelist
  settings     = var.rds
}

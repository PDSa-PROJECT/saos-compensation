module "vpc" {
  source = "./modules/aws/vpc"

  providers = {
    aws = aws
  }

  name_prefix           = var.project_name
  cidr_block            = var.vpc_cidr
  public_subnet_newbits = var.public_subnet_newbits
}

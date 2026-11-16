variable "aws_region" {
  description = "Deployment region; independent of the S3 state bucket region."
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Prefix for project resource names and the Project tag."
  type        = string
  default     = "saos-compensation"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,39}$", var.project_name))
    error_message = "Project name must start with a lowercase letter and contain at most 40 lowercase letters, digits or hyphens."
  }
}

variable "tags" {
  description = "Additional AWS tags; project ownership tags take precedence."
  type        = map(string)
  default     = {}
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the dedicated project VPC."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "VPC CIDR must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_newbits" {
  description = "Additional prefix bits for two non-overlapping public subnets derived from the VPC CIDR."
  type        = number
  default     = 8

  validation {
    condition     = var.public_subnet_newbits >= 1 && floor(var.public_subnet_newbits) == var.public_subnet_newbits
    error_message = "Subnet prefix extension must be a positive integer."
  }
}

variable "name_prefix" {
  description = "Prefix for network resource names."
  type        = string
}

variable "cidr_block" {
  description = "IPv4 CIDR for the dedicated VPC."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.cidr_block))
    error_message = "VPC CIDR must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_newbits" {
  description = "Additional prefix bits used to derive two public subnet CIDRs."
  type        = number

  validation {
    condition = (
      var.public_subnet_newbits >= 1 &&
      floor(var.public_subnet_newbits) == var.public_subnet_newbits &&
      can(cidrnetmask(cidrsubnet(var.cidr_block, var.public_subnet_newbits, 1))) &&
      try(tonumber(split("/", cidrsubnet(var.cidr_block, var.public_subnet_newbits, 1))[1]) <= 28, false)
    )
    error_message = "Subnet prefix extension must produce at least two valid IPv4 subnets with prefixes no longer than /28."
  }
}

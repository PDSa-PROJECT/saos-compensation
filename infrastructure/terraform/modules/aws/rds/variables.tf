variable "name_prefix" {
  description = "Prefix for database resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC containing the database subnets."
  type        = string
}

variable "subnet_ids" {
  description = "Database subnet IDs spanning at least two availability zones."
  type        = list(string)

  validation {
    condition     = length(distinct(var.subnet_ids)) >= 2
    error_message = "RDS requires at least two distinct subnet IDs."
  }
}

variable "ip_whitelist" {
  description = "Public IPv4 CIDRs permitted to connect to PostgreSQL; an empty WHITELIST blocks all clients."
  type        = set(string)

  validation {
    condition = alltrue([
      for cidr in var.ip_whitelist : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) > 0, false)
    ])
    error_message = "Every IP WHITELIST entry must be an IPv4 CIDR; /0 is forbidden."
  }
}

variable "settings" {
  description = "Database sizing and lifecycle settings; no credentials are accepted."
  type = object({
    engine_version            = optional(string, "17")
    instance_class            = optional(string, "db.t4g.micro")
    allocated_storage         = optional(number, 20)
    database_name             = optional(string, "saos")
    master_username           = optional(string, "saos_admin")
    deletion_protection       = optional(bool, true)
    skip_final_snapshot       = optional(bool, true)
    final_snapshot_identifier = optional(string)
  })
  default = {}

  validation {
    condition     = var.settings.allocated_storage >= 20 && floor(var.settings.allocated_storage) == var.settings.allocated_storage
    error_message = "gp3 allocated storage must be an integer of at least 20 GiB."
  }

  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)*$", var.settings.engine_version))
    error_message = "Engine version must be a PostgreSQL major or numeric minor version."
  }

  validation {
    condition     = var.settings.skip_final_snapshot || try(length(trimspace(var.settings.final_snapshot_identifier)) > 0, false)
    error_message = "Set a final snapshot identifier when final snapshots are enabled."
  }
}

terraform {
  backend "s3" {
    bucket       = "saos-infra-tf-state-bucket-549048581262-eu-north-1-an"
    key          = "saos-compensation/terraform.tfstate"
    region       = "eu-north-1"
    encrypt      = true
    use_lockfile = true
  }
}

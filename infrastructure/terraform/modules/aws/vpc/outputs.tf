output "vpc_id" {
  description = "Dedicated VPC ID."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs in stable order, ready after internet routing is configured."
  value       = [for key in sort(keys(aws_subnet.public)) : aws_subnet.public[key].id]
  depends_on  = [aws_route.internet, aws_route_table_association.public]
}

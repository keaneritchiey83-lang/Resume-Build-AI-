output "api_url" {
  value = "http://${aws_lb.main.dns_name}"
}

output "postgres_endpoint" {
  value = aws_db_instance.postgres.address
}

output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "kms_key_arn" {
  value = aws_kms_key.career.arn
}

output "credential_signing_kms_arn" {
  value = aws_kms_key.credential_signing.arn
}

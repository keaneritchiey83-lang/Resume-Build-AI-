output "api_fqdn" {
  value = azurerm_container_app.api.ingress[0].fqdn
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "redis_hostname" {
  value = azurerm_managed_redis.main.hostname
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "container_registry" {
  value = azurerm_container_registry.main.login_server
}

output "redis_port" {
  value = azurerm_managed_redis.main.default_database[0].port
}

output "credential_signing_key_id" {
  value = azurerm_key_vault_key.credential_signing.id
}

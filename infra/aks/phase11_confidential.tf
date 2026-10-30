resource "azurerm_kubernetes_cluster_node_pool" "confidential" {
  count                 = var.confidential_node_pool_enabled ? 1 : 0
  name                  = "confcomp"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = var.confidential_node_vm_size
  vnet_subnet_id        = var.aks_subnet_id
  auto_scaling_enabled  = true
  min_count             = var.confidential_node_min_count
  max_count             = var.confidential_node_max_count
  os_type               = "Linux"

  node_labels = {
    "career.ai/node-pool"            = "confidential"
    "career.ai/confidential-compute" = "true"
  }

  node_taints = [
    "career.ai/confidential=true:NoSchedule"
  ]

  upgrade_settings {
    max_surge = "33%"
  }
}

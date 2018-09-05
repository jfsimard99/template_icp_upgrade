variable "vm_os_password" {
  type = "string"
}

variable "vm_os_user" {
  type = "string"
}

variable "icp_private_ssh_key" {
  type = "string"
  default = ""
}

variable "boot_vm_ipv4_address" {
  type = "string"
}

variable "new_icp_version" {
  type = "string"
  default = "2.1.0.3"
}

variable "new_icp_binary_url" {
  type = "string"
}

variable "download_user" {
  type = "string"
}

variable "download_user_password" {
  type = "string"
}

variable "cluster_location" {
  type = "string"
}

variable "icp_cluster_name" {
  type = "string"
  default = "mycluster"
}

variable "master_node_ip" {
  type = "string"
}

variable "kube_apiserver_secure_port" {
  type = "string"
  default = "8001"
}
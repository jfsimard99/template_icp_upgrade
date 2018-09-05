provider "random" {
  version = "~> 1.0"
}

provider "local" {
  version = "~> 1.1"
}

provider "null" {
  version = "~> 1.0"
}

provider "tls" {
  version = "~> 1.0"
}

resource "random_string" "random-dir" {
  length  = 8
  special = false
}

resource "tls_private_key" "generate" {
  algorithm = "RSA"
  rsa_bits  = "4096"
}

resource "null_resource" "create-temp-random-dir" {
  provisioner "local-exec" {
    command = "${format("mkdir -p  /tmp/%s" , "${random_string.random-dir.result}")}"
  }
}

module "icp_upgrade" {
  source                    = "git::https://github.com/IBM-CAMHub-Open/template_icp_modules.git?ref=2.2//config_icp_upgrade"
  private_key                = "${length(var.icp_private_ssh_key) == 0 ? "${tls_private_key.generate.private_key_pem}" : "${var.icp_private_ssh_key}"}"
  vm_os_user                 = "${var.vm_os_user}"
  vm_os_password             = "${var.vm_os_password}"
  boot_node_ip               = "${var.boot_vm_ipv4_address}"
  icp_url                    = "${var.new_icp_binary_url}"
  icp_version                = "${var.new_icp_version}"
  download_user              = "${var.download_user}"
  download_user_password     = "${var.download_user_password}"
  cluster_location           = "${var.cluster_location}"
  icp_cluster_name           = "${var.icp_cluster_name}"
  master_node_ip             = "${var.master_node_ip}"
  kube_apiserver_secure_port = "${var.kube_apiserver_secure_port}"
  #######
  bastion_host               = "${var.bastion_host}"
  bastion_user               = "${var.bastion_user}"
  bastion_private_key        = "${var.bastion_private_key}"
  bastion_port               = "${var.bastion_port}"
  bastion_host_key           = "${var.bastion_host_key}"
  bastion_password           = "${var.bastion_password}"  
}
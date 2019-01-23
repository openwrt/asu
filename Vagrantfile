Vagrant.configure("2") do |config|
  ENV['LC_ALL']="en_US.UTF-8"
  config.vm.box = "debian/stretch64"
  config.vm.box_check_update = false
  config.vm.hostname = "default"
  config.vm.define "default"
  config.vm.provider :virtualbox do |vb|
    vb.name = "default"
  end
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "ansible/site.yml"
  end
  config.vm.provision "shell",
    inline: "sudo apt install htop ranger vim tree bmon tmux curl -y"
end

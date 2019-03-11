Vagrant.configure("2") do |config|
  ENV['LC_ALL']="en_US.UTF-8"
  config.vm.provision "shell",
    inline: "sudo apt install htop ranger vim tree bmon tmux curl -y"
  config.vm.box = "debian/stretch64"
  config.vm.box_check_update = false
  config.vm.hostname = "vagrant"
  config.vm.define "vagrant"
  config.vm.provider :virtualbox do |vb|
    vb.name = "vagrant"
  end
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "ansible/site.yml"
    ansible.groups = {
        "asu-server" => ["vagrant"]
    }
  end
end

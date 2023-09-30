# fdxseld
FDX68 image file selecter service

## INSTALL

    sudo apt install git pip libopenjp2-7 libxslt-dev
    pip install git+https://github.com/tantanGH/fdxseld.git

    sudo apt install iptables-persistent
    sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 6803
    sudo netfilter-persistent save

from __future__ import print_function

import socket
import struct

from sender import MCAST_GRP, MCAST_PORT


IS_ALL_GROUPS = True

def do():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  if IS_ALL_GROUPS:
      # on this port, receives ALL multicast groups
      sock.bind(('', MCAST_PORT))
  else:
      # on this port, listen ONLY to MCAST_GRP
      sock.bind((MCAST_GRP, MCAST_PORT))

  mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)

  sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

  while True:
    # For Python 3, change next line to "print(sock.recv(10240))"
    print(sock.recv(10240))
    break

  sock.setsockopt(socket.SOL_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton(MCAST_GRP) + socket.inet_aton('0.0.0.0'))

if __name__ == '__main__':
  do()
  print('# Done!')
  

import socket
import configparser
import dns
import dns.message
import dns.resolver

def load_blacklist(file_path):
    blacklist = set()
    with open(file_path, 'r') as f:
        for line in f:
            domain = line.strip()
            blacklist.add(domain)
    return blacklist

# check if the domain name is in the black list
def is_blacklisted(query_name, blacklist):
    return query_name[0:len(query_name) - 1] in blacklist

# use the upstream server to resolve a domain name
def resolve_domain(query_name, upstream_dns_server):
    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.nameservers = [upstream_dns_server[0]]
    try:
        response = resolver.resolve(query_name, 'A') # query
        return response
    # except dns.resolver.NXDOMAIN:
    except Exception as e:
        return None

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    # separate file for the black list, it's easy to put the domain names into the 'config.ini'
    blacklist_file = config['DNS']['blacklist_file']
    upstream_dns_server = (config['DNS']['upstream_dns_server'], 53)
    default_response = config['DNS']['default_response']
    blacklist = load_blacklist(blacklist_file)

    # UDP connection
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # receiving DNS-clients' requests on a standard port
    proxy_socket.bind(('127.0.0.1', 53))  # Привязка к стандартному порту DNS

    print("DNS Proxy is listening...")

    while True:
        data, client_address = proxy_socket.recvfrom(1024)

        query = dns.message.from_wire(data)
        query_name = query.question[0].name.to_text()

        # check if the domain name is in the black list
        if is_blacklisted(query_name, blacklist):
            response = dns.message.make_response(query)
            response.set_rcode(dns.rcode.NXDOMAIN) # !

            # setting default response for tha case of the blocked domain names
            txt_record = dns.rrset.from_text(query_name, 300, dns.rdataclass.IN, dns.rdatatype.TXT, default_response)
            response.answer.append(txt_record)

            response.id = query.id

            proxy_socket.sendto(response.to_wire(), client_address)
        else:
            upstream_response = resolve_domain(query_name, upstream_dns_server)
            if upstream_response is None:
                response = dns.message.make_response(query)
                # returning text 'Not found' if the upstream server cannot find the domain name IP-address
                response.answer.append(
                    dns.rrset.from_text(query_name, 300, dns.rdataclass.IN, dns.rdatatype.TXT, 'Not found'))

                response.id = query.id

                proxy_socket.sendto(response.to_wire(), client_address)
            else:
                # returning the answer of the upstream server to the client
                response = upstream_response
                response.response.id = query.id
                proxy_socket.sendto(response.response.to_wire(), client_address)


if __name__ == "__main__":
    main()

"""
For some queries the code gives an error:
ConnectionResetError: [WinError 10054] Удаленный хост принудительно разорвал существующее подключение
But when I test the code with "dig [domain.name]" with the same domain name, it returns the result to dig.
So it seems that the client programs on my computer need some specific answer format and they don't
accept my format.
The server is asked for a domain name several times, all the times it returns answer, but then the client
interrupts the connection.
Will try to do more to find out the solution, if it's possible.
"""
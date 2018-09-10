"""Michal Bochnak, hw2, CS 450, UIC"""
#
# hw2.py
#
# Michal Bochnak
# CS 450
# Feb 16, 2018
#
# Program downloads the webpage for requested URL.
# It handles HTTP, HTTPS, chunked websites, redirection.
#


# import statements
import logging
import socket
import sys
import ssl
from urllib.parse import urlparse


# receives header, returns status code
def extract_status_code(header):
    """extract_status_code(header) - returns status code extracted from
    header"""
    header_as_str = str(header, 'utf-8')
    code = header_as_str[9] + header_as_str[10] + header_as_str[11]
    return code


# extracts header from the response
def extract_header(response):
    """extract_header(response) - returns header portion of the response"""
    end_of_header = response.find(b'\r\n\r\n')
    return response[0:end_of_header]


# checks if header specifies that data is chunked
def is_chunked(header):
    """is_chunked(header) - true id header specifies that data is chunked,
    false otherwise"""
    return header.find(b'Transfer-Encoding: chunked') != -1


# extracts content lenght from the header
def extract_content_length(header):
    """extract_content_length(header) - extracts content length from the
    header"""
    header_str = str(header, 'utf-8')
    content_length_start = header_str.find('Content-Length: ')
    # not provided
    if content_length_start == -1:
        return -1
    else:
        # skip "Content-Length: " text
        content_length_start += 16
        length_index = content_length_start
        content_length = ''
        while header_str[length_index] != '\r':
            content_length += header_str[length_index]
            length_index += 1

        return int(content_length)


# processed unchunked response
def process_unchunked(skt, content, content_length):
    """process_unchunked(skt, content, content_length) - processed
    unchunked response,
    returns bytes received """
    # content_length given
    if content_length != -1:
        while len(content) < content_length:
            content += skt.recv(4096)
    # content length not given
    else:
        while content.find(b'</html>\r\n' == -1):
            content += skt.recv(4096)

    return content


# extracts chunk size
def extract_chunk_size(_bytes):
    """extract_chunk_size(bytes) - return size of the chunk as integer"""
    size_end = _bytes.find(b'\r\n')
    size_str = str(_bytes[0:size_end], 'utf-8')
    return int(size_str, 16)


# processes chunked response
# response without header must be provided
def process_chunked(skt, response):
    """process_chunked(skt, response) - processes chunked response,
    returns bytes received"""
    content = b''
    line_start = 0

    # make sure there is enough bytes to reach "\r\n"
    while response.find(b'\r\n', line_start) == -1:
        response = response + skt.recv(4096)

    line_end = response.find(b'\r\n')
    # extract chunk size from the line
    chunk_size = extract_chunk_size(response[line_start:line_end + 2])
    # make sure there is at least as many bytes as size of the chunk

    response = response[line_end+2:]

    # keep appending bytes until size of chunk is 0,
    # which means end of data
    while chunk_size != 0:

        # make sure there is at least as many bytes as chunk_size
        while len(response) <= chunk_size:
            response = response + skt.recv(4096)

        # append bytes
        content = content + response[:chunk_size]

        # update response content
        response = response[chunk_size + 2:]

        # make sure there is enough bytes to reach "\r\n"
        while response.find(b'\r\n') < 0:
            response = response + skt.recv(4096)

        # get size
        chunk_size = extract_chunk_size(response)

        # update response
        response = response[response.find(b'\r\n') + 2:]

    return content


# extracts redirection url/param from the header
def extract_redirection_data(header):
    """extract_redirection_data(header) - extracts "Location: " value
    from header"""
    start_index = header.find(b'Location') + 10
    end_index = header.find(b'\r\n', start_index)
    end_index = end_index
    return str(header[start_index:end_index], 'utf-8')


# process a requested url
def retrieve_url(url):
    """retrieve_url(url) - returns content of requested URL, if eny errors occur
    'None' is returned"""

    # default server port
    server_port = 80
    # get values from URL
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    path = parsed_url.path

    # if no path given put '/' into path variable
    if path == '':
        path = '/'

    # update serverPort if specified
    if parsed_url.port is not None:
        server_port = parsed_url.port

    # update port for https connection
    if parsed_url.scheme == 'https':
        server_port = 443

    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # https connection, validate certificate, return 'None" if any errors occur
    if server_port == 443:
        try:
            context = ssl.create_default_context()
            skt = context.wrap_socket(skt, server_hostname=hostname)
            skt.connect((hostname, server_port))
        except ssl.CertificateError:
            return None
        except ssl.SSLError:
            return None
    else:
        try:
            skt.connect((hostname, server_port))
        except socket.error:
            return None

    # construct and send request
    rqst = ('GET ' + path + ' HTTP/1.1\r\nHost: ' + hostname +
            '\r\nConnection: close\r\n\r\n').encode('ascii')

    skt.send(rqst)
    response = skt.recv(4096)

    # make sure there is enough bytes for the whole header
    while response.find(b'\r\n\r\n') == -1:
        response = response + skt.recv(4096)

    # extract particular parts from response
    header = extract_header(response)
    status_code = int(extract_status_code(header))
    content = response[len(header) + 4:]

    # error, not found
    if status_code >= 400:
        return None
    # redirection
    elif status_code == 301:
        redir_data = extract_redirection_data(header)
        # not host, but parameter given, build url
        if redir_data[0] == '/':
            redir_url = parsed_url.scheme + '://' + hostname + redir_data
        else:
            redir_url = redir_data
        return retrieve_url(redir_url)
    # found
    elif status_code == 302:
        if is_chunked(header):
            # process chunked
            return process_chunked(skt, content)
        else:
            # process unchunked
            return process_unchunked(skt, content,
                                     extract_content_length(header))
    # status OK
    elif status_code == 200:
        if is_chunked(header):
            # process chunked
            return process_chunked(skt, content)
        else:
            # process unchunked
            return process_unchunked(skt, content,
                                     extract_content_length(header))
    else:
        return None

mimes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain'
}

def get_mime(file_name):
    """
    Возвращает тип содержимого по имени файла 
    """
    for key in mimes.keys():
        if file_name.find(key) > 0:
            return mimes[key]
    return 'text/plain'
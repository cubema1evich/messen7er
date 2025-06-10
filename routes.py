from views import (
    View, IndexView, GetUserIdView, GetMessageView, SendMessageView,
    RegisterView, LoginView, GetGroupMessagesView, CheckMessagesView,
    CheckEditedMessagesView, CreateGroupView, AddToGroupView, LeaveGroupView,
    GetGroupsView, SendPrivateMessageView, GetPrivateMessagesView,
    CheckGroupsUpdatesView, EditMessageView, CheckPrivateChatsUpdatesView, DeleteMessageView,
    SearchUsersView, GetPrivateChatsView, SearchMessagesView,
    GetGroupMembersView, CheckGroupAccessView, SendSystemMessageView,
    ChangeMemberRoleView, RenameGroupView, RemoveFromGroupView,
    GetGeneralMembersView, NotFoundView, ForbiddenView, InternalServerErrorView, PublicKeyView
)

routes = {
    '/static/': View,
    '^/favicon.ico$': View,
    '^/$': IndexView,  
    '/get_user_id': GetUserIdView,
    '/get_messages': GetMessageView,
    '/send_message': SendMessageView,
    '/register': RegisterView,
    '/login': LoginView,
    '/get_group_messages': GetGroupMessagesView,
    '/check_messages': CheckMessagesView,
    '/check_edited_messages': CheckEditedMessagesView,
    '/check_groups_updates': CheckGroupsUpdatesView,
    '/check_private_chats_updates': CheckPrivateChatsUpdatesView,
    '/create_group': CreateGroupView,
    '/add_to_group': AddToGroupView,
    '/leave_group': LeaveGroupView,
    '/get_groups': GetGroupsView,
    '/send_private_message': SendPrivateMessageView,
    '/get_private_messages': GetPrivateMessagesView,
    '/search_users': SearchUsersView,
    '/get_private_chats': GetPrivateChatsView,
    '/search_messages': SearchMessagesView,
    '/get_group_members': GetGroupMembersView,
    '/check_group_access': CheckGroupAccessView,
    '/get_general_chat_members': GetGeneralMembersView,
    '/send_system_message': SendSystemMessageView,
    '/change_member_role': ChangeMemberRoleView,
    '/rename_group': RenameGroupView,
    '/remove_from_group': RemoveFromGroupView,
    '/check_groups_updates': CheckGroupsUpdatesView,
    '/public_key.pem': PublicKeyView,
    r'^/get_general_members$': GetGeneralMembersView,
    r'^/edit_message/(\d+)$': EditMessageView,
    r'^/delete_message/(\d+)$': DeleteMessageView,
    r'^/404$': NotFoundView,
    r'^/403$': ForbiddenView,
    r'^/500$': InternalServerErrorView
}


def route(url):
    """
    Преобразовывает URL в путь к файлу в соответствии с определенными маршрутами.
    """
    for key in routes.keys():
        if url.startswith(key):
            return routes[key] + url[len(key):]
        return url
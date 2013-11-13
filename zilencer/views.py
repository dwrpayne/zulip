from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.views import login as django_login_page
from django.http import HttpResponseRedirect

from zerver.decorator import has_request_variables, REQ, json_to_dict
from zerver.lib.actions import internal_send_message
from zerver.lib.response import json_success, json_error, json_response, json_method_not_allowed
from zerver.lib.rest import rest_dispatch as _rest_dispatch
from zerver.models import get_realm, get_user_profile_by_email, email_to_domain, \
        UserProfile


rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))


def get_ticket_number():
    fn = '/var/tmp/.feedback-bot-ticket-number'
    try:
        ticket_number = int(open(fn).read()) + 1
    except:
        ticket_number = 1
    open(fn, 'w').write('%d' % ticket_number)
    return ticket_number

@has_request_variables
def submit_feedback(request, deployment, message=REQ(converter=json_to_dict)):
    domainish = message["sender_domain"]
    if get_realm("zulip.com") not in deployment.realms.all():
        domainish += " via " + deployment.name
    subject = "feedback: %s (%s)" % (message["sender_email"], domainish)

    if len(subject) > 60:
        subject = subject[:57].rstrip() + "..."


    ticket_number = get_ticket_number()
    content = '@support, Please ack this new request.'
    content += '\n~~~'
    content += '\nticket Z%03d' % (ticket_number,)
    content += '\nsender: %s' % (message['sender_full_name'],)
    content += '\nemail: %s' % (message['sender_email'],)
    if 'sender_domain' in message:
        content += '\nrealm: %s' % (message['sender_domain'],)
    content += '\n~~~'

    content += '\n\n'
    content += message['content']

    internal_send_message("feedback@zulip.com", "stream", "support", subject, content)

    return HttpResponse(message['sender_email'])


def realm_for_email(email):
    try:
        user = get_user_profile_by_email(email)
        return user.realm
    except UserProfile.DoesNotExist:
        pass

    return get_realm(email_to_domain(email))

# Requests made to this endpoint are UNAUTHENTICATED
@csrf_exempt
@has_request_variables
def lookup_endpoints_for_user(request, email=REQ()):
    try:
        return json_response(realm_for_email(email).deployment.endpoints)
    except AttributeError:
        return json_error("Cannot determine endpoint for user.", status=404)

def account_deployment_dispatch(request, **kwargs):
    sso_unknown_email = False
    if request.method == 'POST':
        email = request.POST['username']
        realm = realm_for_email(email)
        try:
            return HttpResponseRedirect(realm.deployment.base_site_url)
        except AttributeError:
            # No deployment found for this user/email
            sso_unknown_email = True

    template_response = django_login_page(request, **kwargs)
    template_response.context_data['sso_only'] = True
    template_response.context_data['sso_unknown_email'] = sso_unknown_email
    return template_response

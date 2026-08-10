import strawberry
from django.conf import settings
from strawberry.extensions import DisableIntrospection

from selahcue_api.graphql.context import actor_from_info, require_customer_org


@strawberry.type
class AccountViewer:
    surface: str
    actor_id: str
    org_id: str


@strawberry.type
class AccountQuery:
    @strawberry.field
    def account_viewer(self, info: strawberry.Info) -> AccountViewer:
        actor = actor_from_info(info)
        checked = require_customer_org(actor, actor.org_id if actor else "")
        return AccountViewer(surface="account", actor_id=checked.actor_id, org_id=checked.org_id or "")


schema = strawberry.Schema(
    query=AccountQuery,
    extensions=[] if settings.GRAPHQL_INTROSPECTION_ENABLED else [DisableIntrospection],
)

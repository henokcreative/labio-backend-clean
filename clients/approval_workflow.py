from .models import Approval, ProjectFile


def actionable_approvals_for_client(client):
    """Return pending approval actions owned by the client's file projects."""
    return Approval.objects.filter(
        client=client,
        file__project__client=client,
        file__category=ProjectFile.Category.APPROVAL,
        status=Approval.Status.PENDING,
    )

import React, { useMemo, useState } from 'react';
import { Table, Button, Modal, Form, Input, Popconfirm, message, Space } from 'antd';
import { useQuery} from '@tanstack/react-query';
import { DomainRead, DomainCreate, DomainUpdate } from '../types/schemas';
import { createDomain, getDomains, updateDomain, deleteDomain, validateDomain, scanDomains } from '../api/domain.api';
import { useModalForm } from '../hooks/useModalForm'; 
import { useTranslation } from 'react-i18next';
import{  useApiMutation } from '../hooks/useApiMutation';

const DomainManagement: React.FC = () => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [isValidating, setIsValidating] = useState(false);
  const { isModalOpen, editingItem, openCreateModal, openEditModal, handleCancel } = useModalForm<DomainRead>({
    form,
    defaultValues: {
      server_url: 'server.com',
      ad_base_dn: 'DC=example,DC=com',
    },
  });

  // Запит для отримання списку доменів
  const { data: domains = [], refetch, isLoading } = useQuery<DomainRead[]>({
    queryKey: ['domains'],
    queryFn: getDomains,
    enabled: true,
    staleTime: 60 * 60 * 1000, // Дані свіжі протягом 1 години
    gcTime: 60 * 60 * 1000, // Кеш зберігається 1 годину
    refetchOnWindowFocus: false, // Вимикаємо повторний запит при фокусі
  });


  const { mutate: createMutate, isPending: isCreating } = useApiMutation({
    mutationFn: (payload: DomainCreate) => createDomain(payload),
    successMessage: t('domain_created'),
    invalidateQueryKeys: [['domains']],
    onSuccessCallback: () => handleCancel(),
  });

  const { mutate: validateMutate, isPending: isValidatingConnection } = useApiMutation({
    mutationFn: (payload: DomainCreate) => validateDomain(payload),
    successMessage: t('connection_validated', { message: '{message}' }), // Placeholder для форматування
    onSuccessCallback: (data: any) => {
      // Форматуємо повідомлення з даними
      message.success(t('connection_validated', { message: data.message }));
    },
  });

  const { mutate: scanDomainsMutate, isPending: isDomainADScanLoading } = useApiMutation({
    mutationFn: (domainId?: number) => scanDomains(domainId),
    onSuccessCallback: (data: any) => {
      if (data.task_id) {
        message.success(t('domain_scan_started', { task_id: data.task_id }));
      } else if (data.task_ids) {
        message.success(t('scan_all_domains_started', { task_ids: data.task_ids.join(', ') }));
      }
    },
    errorMessage: t('domain_scan_error'),
  });

  const { mutate: updateMutate, isPending: isUpdating } = useApiMutation({
    mutationFn: ({ id, data }: { id: number; data: DomainUpdate }) => updateDomain(id, data),
    successMessage: t('domain_updated'),
    invalidateQueryKeys: [['domains']],
    onSuccessCallback: () => handleCancel(),
  });

  const { mutate: deleteMutate, isPending: isDeleting } = useApiMutation({
    mutationFn: (id: number) => deleteDomain(id),
    successMessage: t('domain_deleted'),
    invalidateQueryKeys: [['domains']],
  });

  // Перевірка зв’язку
  const handleValidate = async () => {
    try {
      setIsValidating(true);
      const values = await form.validateFields();
      const payload: DomainCreate = {
        name: values.name,
        username: values.username,
        password: values.password,
        server_url: values.server_url,
        ad_base_dn: values.ad_base_dn,
      };
      validateMutate(payload);
    } catch (error: any) {
      // Обробка помилок валідатора форми
      message.error(error.message || t('error'));
    } finally {
      setIsValidating(false);
    }
  };

  // Обробка відправлення форми
  const onFinish = async () => {
    try {
      const values = await form.validateFields();
      const payload: DomainUpdate = {
        id: editingItem ? editingItem.id : 0,
        name: values.name,
        username: values.username,
        password: values.password,
        server_url: values.server_url,
        ad_base_dn: values.ad_base_dn,
        last_updated: null,
      };
      if (editingItem) {
        updateMutate({ id: editingItem.id, data: payload });
      } else {
        const { id, last_updated, ...createPayload } = payload;
        createMutate(createPayload as DomainCreate);
      }
    } catch (error: any) {
      // Обробка помилок валідатора форми
      message.error(error.message || t('error'));
    }
  };
  
  // Колонки таблиці
  const columns = useMemo(
    () => [
      { title: t('domain'), dataIndex: 'name', key: 'name', sorter: (a: DomainRead, b: DomainRead) => a.name.localeCompare(b.name) },
      { title: t('username'), dataIndex: 'username', key: 'username', sorter: (a: DomainRead, b: DomainRead) => a.username.localeCompare(b.username) },
      { title: t('server_url'), dataIndex: 'server_url', key: 'server_url' },
      { title: t('ad_base_dn'), dataIndex: 'ad_base_dn', key: 'ad_base_dn' },
      { title: t('last_updated'), dataIndex: 'last_updated', key: 'last_updated' },
      {
        title: t('actions'),
        key: 'actions',
        render: (_: any, record: DomainRead) => (
          <Space>
            <Button onClick={() => openEditModal(record)} aria-label={t('edit_domain', { name: record.name })}>
              {t('edit')}
            </Button>
            <Button
              onClick={() => scanDomainsMutate(record.id)}
              loading={isDomainADScanLoading}
              disabled={isDomainADScanLoading}
              aria-label={t('scan_domain', { name: record.name })}
            >
              {t('scan_domain')}
            </Button>
            <Popconfirm
              title={t('confirm_delete_domain')}
              onConfirm={() => deleteMutate(record.id)}
              okText={t('yes')}
              cancelText={t('no')}
            >
              <Button danger loading={isDeleting} aria-label={t('delete_domain', { name: record.name })}>
                {t('delete')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [isDeleting, isDomainADScanLoading, deleteMutate, openEditModal, scanDomainsMutate, t]
  );

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreateModal} aria-label={t('add_domain')}>
          {t('add_domain')}
        </Button>
      </Space>

      <Table
        dataSource={domains}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        aria-label={t('domains_table')}
      />

      <Modal
        title={editingItem ? t('edit_domain_title') : t('new_domain')}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel} aria-label={t('cancel')}>
            {t('cancel')}
          </Button>,
          <Button
            key="validate"
            loading={isValidatingConnection}
            onClick={handleValidate}
            aria-label={t('validate_connection')}
          >
            {t('validate_connection')}
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isCreating || isUpdating}
            onClick={() => form.submit()}
            aria-label={editingItem ? t('save_domain_changes') : t('create_domain')}
          >
            {editingItem ? t('save') : t('create')}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="name"
            label={t('domain')}
            rules={[
              { required: true, message: t('enter_domain') },
              { whitespace: true, message: t('no_whitespace') },
              {
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$/,
                message: t('invalid_domain_format'),
              },
            ]}
          >
            <Input placeholder={t('domain_placeholder')} />
          </Form.Item>
          <Form.Item
            name="username"
            label={t('username')}
            rules={[
              { required: true, message: t('enter_username') },
              { whitespace: true, message: t('no_whitespace') },
            ]}
            tooltip={editingItem ? t('username_format_tip') : undefined}
          >
            <Input placeholder={t('username_placeholder')} />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingItem ? t('new_password') : t('password')}
            rules={editingItem ? [
              { whitespace: true, message: t('no_whitespace') },
            ] : [
              { required: true, message: t('enter_password') },
              { whitespace: true, message: t('no_whitespace') },
            ]}
            tooltip={editingItem ? t('password_change_tip') : undefined}
          >
            <Input.Password placeholder={t('password_placeholder')} />
          </Form.Item>
          <Form.Item
            name="server_url"
            label={t('server_url')}
            rules={[
              { required: true, message: t('enter_server_url') },
              { whitespace: true, message: t('no_whitespace') },
              {
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$/,
                message: t('invalid_server_url_format'),
              },
            ]}
          >
            <Input placeholder={t('server_url_placeholder')} />
          </Form.Item>
          <Form.Item
            name="ad_base_dn"
            label={t('ad_base_dn')}
            rules={[
              { required: true, message: t('enter_ad_base_dn') },
              { whitespace: true, message: t('no_whitespace') },
            ]}
          >
            <Input placeholder={t('ad_base_dn_placeholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DomainManagement;
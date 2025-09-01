import React, { useMemo, useCallback, useState } from 'react';
import { Table, Button, Modal, Form, Input, Popconfirm, message, Space } from 'antd';
import { useQuery, useMutation } from '@tanstack/react-query';
import { DomainRead, DomainCreate, DomainUpdate } from '../types/schemas';
import { createDomain, getDomains, updateDomain, deleteDomain, validateDomain, scanDomains } from '../api/domain.api';
import { useModalForm } from '../hooks/useModalForm'; 

// Утилітна функція для уніфікованої обробки помилок
const getErrorMessage = (error: Error | any): string => {
  if (error.response?.data?.detail) {
    if (Array.isArray(error.response.data.detail)) {
      return error.response.data.detail
        .map((err: { msg: string; loc: string[] }) => `${err.loc.join('.')}: ${err.msg}`)
        .join('; ');
    }
    return error.response.data.detail;
  }
  return error.message || 'Невідома помилка';
};

const DomainManagement: React.FC = () => {
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

  // Мутації
  const { mutate: createMutate, isPending: isCreating } = useMutation({
    mutationFn: (payload: DomainCreate) => createDomain(payload),
    onSuccess: () => {
      message.success('Домен створено');
      refetch();
      handleCancel();
    },
    onError: (error: Error) => message.error(getErrorMessage(error)),
  });

  const { mutate: validateMutate, isPending: isValidatingConnection } = useMutation({
    mutationFn: (payload: DomainCreate) => validateDomain(payload),
    onSuccess: (result) => message.success(result.message),
    onError: (error: Error) => message.error(getErrorMessage(error)),
  });

  const { mutate: scanDomainsMutate, isPending: isDomainADScanLoading } = useMutation({
    mutationFn: (domainId?: number) => scanDomains(domainId),
    onSuccess: (data) => {
      if (data.task_id) {
        message.success(`Сканування AD для домену запущено, task_id: ${data.task_id}`);
      } else if (data.task_ids) {
        message.success(`Сканування всіх доменів запущено, task_ids: ${data.task_ids.join(', ')}`);
      }
    },
    onError: (error: Error) => message.error(`Помилка сканування AD: ${getErrorMessage(error)}`),
  });

  const { mutate: updateMutate, isPending: isUpdating } = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DomainUpdate }) => updateDomain(id, data),
    onSuccess: () => {
      message.success('Домен оновлено');
      refetch();
      handleCancel();
    },
    onError: (error: Error) => message.error(getErrorMessage(error)),
  });

  const { mutate: deleteMutate, isPending: isDeleting } = useMutation({
    mutationFn: (id: number) => deleteDomain(id),
    onSuccess: () => {
      message.success('Домен видалено');
      refetch();
    },
    onError: (error: Error) => message.error(getErrorMessage(error)),
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
      message.error(getErrorMessage(error));
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
      message.error(getErrorMessage(error));
    }
  };

  // Колонки таблиці
  const columns = useMemo(
    () => [
      { title: 'Домен', dataIndex: 'name', key: 'name', sorter: (a: DomainRead, b: DomainRead) => a.name.localeCompare(b.name) },
      { title: 'Користувач', dataIndex: 'username', key: 'username', sorter: (a: DomainRead, b: DomainRead) => a.username.localeCompare(b.username) },
      { title: 'URL сервера', dataIndex: 'server_url', key: 'server_url' },
      { title: 'AD Base DN', dataIndex: 'ad_base_dn', key: 'ad_base_dn' },
      { title: 'Оновлено', dataIndex: 'last_updated', key: 'last_updated' },
      {
        title: 'Дії',
        key: 'actions',
        render: (_: any, record: DomainRead) => (
          <Space>
            <Button onClick={() => openEditModal(record)} aria-label={`Редагувати домен ${record.name}`}>
              Редагувати
            </Button>
            <Button
              onClick={() => scanDomainsMutate(record.id)}
              loading={isDomainADScanLoading}
              disabled={isDomainADScanLoading}
              aria-label={`Опитати домен ${record.name}`}
            >
              Опитати домен
            </Button>
            <Popconfirm
              title="Впевнені, що хочете видалити домен?"
              onConfirm={() => deleteMutate(record.id)}
              okText="Так"
              cancelText="Ні"
            >
              <Button danger loading={isDeleting} aria-label={`Видалити домен ${record.name}`}>
                Видалити
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [isDeleting, isDomainADScanLoading, deleteMutate, openEditModal, scanDomainsMutate]
  );

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreateModal} aria-label="Додати новий домен">
          Додати домен
        </Button>
        <Button onClick={() => refetch()} aria-label="Оновити список доменів">
          Оновити список
        </Button>
      </Space>

      <Table
        dataSource={domains}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        aria-label="Таблиця доменів"
      />

      <Modal
        title={editingItem ? 'Редагування домену' : 'Новий домен'}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel} aria-label="Скасувати">
            Відміна
          </Button>,
          <Button
            key="validate"
            loading={isValidatingConnection}
            onClick={handleValidate}
            aria-label="Перевірити зв’язок з доменом"
          >
            Перевірити зв’язок
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={isCreating || isUpdating}
            onClick={() => form.submit()}
            aria-label={editingItem ? 'Зберегти зміни домену' : 'Створити домен'}
          >
            {editingItem ? 'Зберегти' : 'Створити'}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="name"
            label="Домен"
            rules={[
              { required: true, message: 'Введіть назву домену' },
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
              {
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$/,
                message: 'Домен має містити лише літери, цифри, дефіси та точки (наприклад, example.com)',
              },
            ]}
          >
            <Input placeholder="Наприклад, example.com" />
          </Form.Item>
          <Form.Item
            name="username"
            label="Користувач"
            rules={[
              { required: true, message: 'Введіть ім’я користувача' },
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
            ]}
            tooltip={editingItem ? 'Заповніть у вигляді DOMEN\\USER' : undefined}
          >
            <Input placeholder="Наприклад, admin" />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingItem ? 'Новий пароль (заповніть для зміни)' : 'Пароль'}
            rules={editingItem ? [
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
            ] : [
              { required: true, message: 'Введіть пароль' },
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
            ]}
            tooltip={editingItem ? 'Заповніть це поле, лише якщо хочете змінити пароль' : undefined}
          >
            <Input.Password placeholder="Введіть пароль" />
          </Form.Item>
          <Form.Item
            name="server_url"
            label="URL сервера"
            rules={[
              { required: true, message: 'Введіть URL сервера' },
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
              {
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$/,
                message: 'URL сервера має містити лише літери, цифри, дефіси та точки (наприклад, server.com)',
              },
            ]}
          >
            <Input placeholder="Наприклад, server.com" />
          </Form.Item>
          <Form.Item
            name="ad_base_dn"
            label="AD Base DN"
            rules={[
              { required: true, message: 'Введіть AD Base DN' },
              { whitespace: true, message: 'Поле не може містити лише пробіли' },
            ]}
          >
            <Input placeholder="Наприклад, DC=example,DC=com" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DomainManagement;